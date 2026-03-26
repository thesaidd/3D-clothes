"""
Celery Task Modulu - Kiyafet Isleme Pipeline'i

ADIM 1 - Orijinal goruntu okunur (S3 URL veya local disk)
ADIM 2 - rembg ile arka plan kaldirilir -> S3'e PNG olarak yuklenir
ADIM 3 - Tripo3D API v2 ile gercek 3D modele donusturulur -> GLB S3'e yuklenir

S3 kullanilamazsa her adim yerel 'uploads/' klasorune yazmaya devam eder (fallback).
"""
import io
import logging
import os
import tempfile
import time
import traceback as tb_module
from pathlib import Path

from app.worker.celery_app import celery

# Tüm ORM modellerini Base metadata'ya kayıt et.
# Celery worker ayağa kalkarken ForeignKey hedef tablolar
# (avatars, garments) zaten bellekte olmalı; aksi halde
# SQLAlchemy NoReferencedTableError fırlatır.
from app.models.garment import Garment   # noqa: F401 — garments tablosunu kayıt et
from app.models.avatar  import Avatar    # noqa: F401 — avatars  tablosunu kayıt et
from app.models.tryon   import TryOn     # noqa: F401 — try_ons  tablosunu kayıt et

logger = logging.getLogger(__name__)

# Yerel fallback klasorleri (S3 yokken kullanilir)
_LOCAL_CLEANED = Path("uploads/cleaned")
_LOCAL_MODELS  = Path("uploads/models")

# S3 path prefixleri
S3_CLEANED_PREFIX = "uploads/cleaned"
S3_MODELS_PREFIX  = "uploads/models"


def _db_update(job_id: str, **fields) -> None:
    """
    Celery worker icinden sorunsuz DB guncelleme.
    PostgreSQL baglanamiyorsa (test/gelistirme ortami) sessizce atlar.
    """
    try:
        from app.db.database import get_db_context
        from app.models.garment import Garment
        from datetime import datetime, timezone

        with get_db_context() as db:
            garment = db.query(Garment).filter(Garment.job_id == job_id).first()
            if garment:
                for key, val in fields.items():
                    setattr(garment, key, val)
                garment.updated_at = datetime.now(timezone.utc)
    except Exception as db_err:
        logger.warning(f"[DB] Guncelleme basarisiz (job_id={job_id}): {db_err}")


# ─────────────────────────────────────────────────────────────────
# Try-On Pipeline Task
# ─────────────────────────────────────────────────────────────────

FALLBACK_TRYON_URL = (
    "https://placehold.co/400x600/1a1a2e/ffffff"
    "?text=HuggingFace+Yogun%0AMock+Gosteriliyor"
)

# Cinsiyet bazlı telifsiz manken fotoğrafları (Unsplash)
_MANNEQUIN_URLS = {
    "female": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=400&q=80",
    "male":   "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=400&q=80",
    "unisex": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=400&q=80",
}


@celery.task(
    bind=True,
    name="tasks.process_tryon_task",
    max_retries=1,
    default_retry_delay=5,
    soft_time_limit=120,   # 2 dk — HF Space yavaş olabilir
    time_limit=150,
)
def process_tryon_task(self, tryon_id: str):
    """
    V4 — Sanal Deneme (Try-On) Arka Plan Görevi

    Akış:
      1. TryOn kaydını 'processing' yap.
      2. İlişkili Garment ve Avatar verilerini oku.
      3. Hugging Face IDM-VTON Space'e gradio_client ile çağrı yap.
      4. Başarılı → result_url = HF sonucu → completed
         Hata/timeout → result_url = fallback placeholder → completed
         (görev *asla* failed olmaz; kullanıcı her zaman bir görsel görür)
    """
    import uuid as _uuid

    log = logging.getLogger(f"tasks.tryon.{tryon_id[:8]}")
    log.info(f"[TryOn {tryon_id}] V4 görevi başladı.")

    # ── 0. Yardımcı: DB'ye güvenli yaz ───────────────────────────
    def _save_result(result_url: str) -> None:
        try:
            from app.db.database import get_db_context
            with get_db_context() as db:
                row = db.query(TryOn).filter(TryOn.id == _uuid.UUID(tryon_id)).first()
                if row:
                    row.status     = "completed"
                    row.result_url = result_url
                    db.commit()
                    log.info(f"[TryOn {tryon_id}] Kaydedildi → {result_url[:60]}…")
        except Exception as db_err:
            log.error(f"[TryOn {tryon_id}] DB yazma hatası: {db_err}")

    # ── 1. Durum: processing ──────────────────────────────────────
    try:
        from app.db.database import get_db_context
        with get_db_context() as db:
            row = db.query(TryOn).filter(TryOn.id == _uuid.UUID(tryon_id)).first()
            if not row:
                log.error(f"[TryOn {tryon_id}] Kayıt bulunamadı.")
                return
            row.status = "processing"
            db.commit()
            # İlişkili verileri oku (session kapanmadan önce)
            avatar_gender  = row.avatar.gender  if hasattr(row, "avatar")  else "female"
            garment_img    = None
            # Avatar ve Garment lazy-load (detached session öncesi)
            avatar_id_val  = row.avatar_id
            garment_id_val = row.garment_id
    except Exception as exc:
        log.exception(f"[TryOn {tryon_id}] DB processing hatası: {exc}")
        return

    # Avatar ve kıyafet bilgilerini ayrı session'da oku
    try:
        from app.db.database import get_db_context
        with get_db_context() as db:
            avatar  = db.query(Avatar).filter(Avatar.id  == avatar_id_val).first()
            garment = db.query(Garment).filter(Garment.id == garment_id_val).first()
            avatar_gender = getattr(avatar,  "gender",      "female") if avatar  else "female"
            garment_img   = getattr(garment, "cleaned_url", None)     if garment else None
            if not garment_img:
                garment_img = getattr(garment, "original_url", None)  if garment else None
    except Exception as exc:
        log.warning(f"[TryOn {tryon_id}] Avatar/Garment okunamadı: {exc}")
        avatar_gender = "female"
        garment_img   = None

    mannequin_url = _MANNEQUIN_URLS.get(avatar_gender, _MANNEQUIN_URLS["female"])
    log.info(f"[TryOn {tryon_id}] Manken: {avatar_gender} | Kıyafet URL: {garment_img}")

    # ── 2. IDM-VTON (Hugging Face Space) Çağrısı ─────────────────
    result_url = FALLBACK_TRYON_URL   # güvenli varsayılan

    if not garment_img:
        log.warning(f"[TryOn {tryon_id}] Kıyafet görseli yok → fallback kullanılıyor.")
        _save_result(result_url)
        return

    try:
        from gradio_client import Client, handle_file
        log.info(f"[TryOn {tryon_id}] HF IDM-VTON bağlantısı kuruluyor…")
        client = Client("yisol/IDM-VTON", verbose=False)

        log.info(f"[TryOn {tryon_id}] IDM-VTON predict() çağrısı yapılıyor…")
        api_result = client.predict(
            dict={
                "background": handle_file(mannequin_url),
                "layers":     [],
                "composite":  None,
            },
            garm_img      = handle_file(garment_img),
            garment_des   = "clothing item",    # kısa açıklama
            is_checked     = True,
            is_checked_crop= False,
            denoise_steps  = 30,
            seed           = 42,
            api_name       = "/tryon",
        )

        # Sonuç: (image_path, mask_path) veya sadece image_path döner
        if isinstance(api_result, (list, tuple)):
            raw = api_result[0]
        else:
            raw = api_result

        # gradio_client yerel dosya yolu veya {'url': ...} döner
        if isinstance(raw, dict) and "url" in raw:
            result_url = raw["url"]
        elif isinstance(raw, str) and raw.startswith("http"):
            result_url = raw
        else:
            # yerel dosya yolu — fallback kullan
            log.warning(f"[TryOn {tryon_id}] Beklenmedik sonuç tipi ({type(raw)}), fallback.")
            result_url = FALLBACK_TRYON_URL

        log.info(f"[TryOn {tryon_id}] IDM-VTON başarılı → {result_url[:60]}…")

    except Exception as hf_err:
        # Timeout, quota aşımı, model yükleme hatası — hepsini yut
        log.warning(
            f"[TryOn {tryon_id}] HF IDM-VTON başarısız "
            f"({type(hf_err).__name__}: {hf_err!s:.120}) → fallback."
        )
        result_url = FALLBACK_TRYON_URL

    # ── 3. Sonucu Kaydet (her durumda completed) ──────────────────
    _save_result(result_url)


# ─────────────────────────────────────────────────────────────────
# Ana Pipeline Task
# ─────────────────────────────────────────────────────────────────

@celery.task(
    bind=True,
    name="tasks.process_garment_image",
    max_retries=2,
    default_retry_delay=10,
)
def process_garment_image(
    self,
    job_id: str,
    image_ref: str,         # S3 URL (https://...) veya yerel yol (uploads/originals/...)
    garment_type: str = "shirt",
    use_s3: bool = False,
    api_key: str = "",     # BYOK: Kullanicinin sagladigi Tripo3D API anahtari (opsiyonel)
):
    """
    Kiyafet fotografini isleyen ana pipeline.

    Args:
        job_id:       Izleme icin benzersiz ID (== Celery task ID)
        image_ref:    S3 public URL veya yerel dosya yolu
        garment_type: Kiyafet turu (ileride kumac simulasyon parametrelerini etkiler)
        use_s3:       True -> S3'e yukle; False -> yerel diske yaz
        api_key:      BYOK - Kullanicinin sagladıgı Tripo3D API key (bos ise .env fallback)
    """
    log = logging.getLogger(f"tasks.pipeline.{job_id[:8]}")

    steps = [
        {"name": "background_removal", "status": "pending", "detail": ""},
        {"name": "tripo3d_conversion",  "status": "pending", "detail": ""},
    ]

    def push_state(step_name: str, progress: int, step_status: str, detail: str = ""):
        for s in steps:
            if s["name"] == step_name:
                s["status"] = step_status
                s["detail"] = detail
        self.update_state(
            state="PROGRESS",
            meta={"step": step_name, "progress": progress, "steps": steps},
        )

    try:
        # ── ADIM 1: Goruntu byt'larini al ────────────────────────
        log.info("Adim 1/3 - Goruntu yukleniyor...")
        _db_update(job_id, status="processing")
        image_bytes = _fetch_image(image_ref, log)
        log.info(f"Goruntu alindi ({len(image_bytes) / 1024:.1f} KB)")

        # ── ADIM 2: Arka Plan Kaldirma (rembg) ───────────────────
        push_state("background_removal", progress=10, step_status="running",
                   detail="rembg modeli yukleniyor...")
        log.info("Adim 2/3 - Arka plan kaldiriliyor (rembg)...")

        cleaned_bytes = _remove_background(image_bytes, log)

        push_state("background_removal", progress=45, step_status="running",
                   detail="Temizlenmis PNG kaydediliyor...")

        # Temizlenmis PNG'yi S3'e veya locale kaydet
        cleaned_ref = _save_cleaned(
            job_id=job_id,
            data=cleaned_bytes,
            use_s3=use_s3,
            log=log,
        )

        push_state("background_removal", progress=50, step_status="done",
                   detail=f"PNG kaydedildi: {cleaned_ref[:80]}")
        log.info(f"Temizlenmis goruntu: {cleaned_ref[:80]}")

        # Temizlenmis goruntu URL'sini DB'ye yaz
        _db_update(job_id, cleaned_url=cleaned_ref)

        # ── ADIM 3: Tripo3D API v2 ile 3D Donusum ────────────────
        push_state("tripo3d_conversion", progress=55, step_status="running",
                   detail="Tripo3D API'ye goruntu yukleniyor...")
        log.info("Adim 3/3 - Tripo3D API v2 entegrasyonu basliyor...")

        # _call_tripo3d icin gecici local dosya lazim (httpx multipart upload)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(cleaned_bytes)
            tmp_path = Path(tmp.name)

        try:
            glb_bytes = _call_tripo3d_bytes(
                job_id=job_id,
                cleaned_path=tmp_path,
                log=log,
                api_key=api_key,
                push_state_fn=lambda p, d: push_state(
                    "tripo3d_conversion", progress=p, step_status="running", detail=d
                ),
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        push_state("tripo3d_conversion", progress=92, step_status="running",
                   detail="GLB modeli kaydediliyor...")

        model_ref = _save_model(
            job_id=job_id,
            data=glb_bytes,
            use_s3=use_s3,
            log=log,
        )

        push_state("tripo3d_conversion", progress=95, step_status="done",
                   detail=f"Model kaydedildi: {model_ref[:80]}")
        log.info(f"Model referansi: {model_ref[:80]}")

        # ── TAMAMLANDI ────────────────────────────────────────────
        result = {
            "progress":           100,
            "step":               "completed",
            "steps":              steps,
            "original_image_url": image_ref,
            "cleaned_image_url":  cleaned_ref,
            "model_url":          model_ref,
        }

        # DB'yi tamamlandi olarak guncelle
        _db_update(
            job_id,
            status    = "completed",
            model_url = model_ref,
        )

        log.info(f"Pipeline tamamlandi - job_id={job_id}")
        return result

    except Exception as exc:
        log.error(f"Pipeline hatasi: {exc}", exc_info=True)
        for s in steps:
            if s["status"] == "running":
                s["status"] = "error"
                s["detail"] = str(exc)

        # DB'yi basarisiz olarak guncelle (o ana kadar uretilen URL'ler korunur)
        _db_update(
            job_id,
            status        = "failed",
            error_message = str(exc)[:500],
        )

        self.update_state(
            state="PIPELINE_FAILED",
            meta={
                "step":      "error",
                "progress":  0,
                "steps":     steps,
                "error":     str(exc),
                "exc_type":  type(exc).__name__,
                "traceback": tb_module.format_exc(limit=10),
            },
        )
        raise


# ─────────────────────────────────────────────────────────────────
# Yardimci: Goruntu Getir (S3 URL veya lokal dosya)
# ─────────────────────────────────────────────────────────────────

def _fetch_image(image_ref: str, log) -> bytes:
    """S3 URL (http/https) ise indir; yerel yol ise diskten oku."""
    if image_ref.startswith("http://") or image_ref.startswith("https://"):
        import httpx
        with httpx.Client(timeout=30) as client:
            r = client.get(image_ref)
        if r.status_code != 200:
            raise RuntimeError(f"S3'ten goruntu indirilemedi: HTTP {r.status_code}")
        log.info(f"S3'ten goruntu indirildi ({len(r.content)/1024:.1f} KB)")
        return r.content
    else:
        p = Path(image_ref)
        if not p.exists():
            raise FileNotFoundError(f"Goruntu bulunamadi: {image_ref}")
        return p.read_bytes()


# ─────────────────────────────────────────────────────────────────
# Yardimci: Temizlenmis PNG'yi Kaydet
# ─────────────────────────────────────────────────────────────────

def _save_cleaned(job_id: str, data: bytes, use_s3: bool, log) -> str:
    """Temizlenmis PNG'yi S3'e veya yerel diske kaydet. Referans URL/yol don."""
    if use_s3:
        from app.services.storage import upload_bytes_to_s3
        s3_key = f"{S3_CLEANED_PREFIX}/{job_id}_clean.png"
        url = upload_bytes_to_s3(data, s3_key, content_type="image/png", presigned=False)
        log.info(f"[S3] Cleaned PNG yuklendi: {s3_key}")
        return url
    else:
        _LOCAL_CLEANED.mkdir(parents=True, exist_ok=True)
        local_path = _LOCAL_CLEANED / f"{job_id}_clean.png"
        local_path.write_bytes(data)
        return str(local_path)


# ─────────────────────────────────────────────────────────────────
# Yardimci: GLB Modelini Kaydet
# ─────────────────────────────────────────────────────────────────

def _save_model(job_id: str, data: bytes, use_s3: bool, log) -> str:
    """GLB bytes'ini S3'e veya yerel diske kaydet. Referans URL/yol don."""
    if use_s3:
        from app.services.storage import upload_bytes_to_s3
        s3_key = f"{S3_MODELS_PREFIX}/{job_id}_model.glb"
        url = upload_bytes_to_s3(
            data, s3_key,
            content_type="model/gltf-binary",
            presigned=False,
        )
        log.info(f"[S3] GLB modeli yuklendi: {s3_key}")
        return url
    else:
        _LOCAL_MODELS.mkdir(parents=True, exist_ok=True)
        local_path = _LOCAL_MODELS / f"{job_id}_model.glb"
        local_path.write_bytes(data)
        return str(local_path)


# ─────────────────────────────────────────────────────────────────
# Yardimci: Arka Plan Kaldirma (rembg)
# ─────────────────────────────────────────────────────────────────

def _remove_background(image_bytes: bytes, log) -> bytes:
    """
    rembg kutuphanesini kullanarak goruntunun arka planini kaldirir.
    Cikti: RGBA transparent PNG bytes.

    Model: 'isnet-general-use' — kiyafet/nesne segmentasyonu icin optimize.
    Ilk cagirda model agirliklariyasiyalarilari (~170 MB) otomatik indirilir.
    """
    from PIL import Image

    try:
        from rembg import remove as rembg_remove, new_session

        session   = new_session("isnet-general-use")
        input_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        output    = rembg_remove(input_img, session=session)

        buf = io.BytesIO()
        output.save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    except ImportError as e:
        raise RuntimeError(
            "rembg kurulu degil. `pip install rembg onnxruntime` calistirin."
        ) from e


# ─────────────────────────────────────────────────────────────────
# Gercek Tripo3D API v2 Entegrasyonu  (bytes donduren versiyon)
# ─────────────────────────────────────────────────────────────────

_TRIPO_BASE    = "https://api.tripo3d.ai/v2/openapi"
_POLL_INTERVAL = 5     # her kac saniyede bir kontrol et
_POLL_TIMEOUT  = 300   # maksimum bekleme suresi (5 dakika)


def _call_tripo3d_bytes(
    job_id: str,
    cleaned_path: Path,
    log,
    push_state_fn,
    api_key: str = "",
) -> bytes:
    """
    Tripo3D API v2 ile tam 3D donusum akisi:
      1. Temizlenmis PNG'yi multipart olarak yukle -> image_token al
      2. image_to_model gorevi olustur -> tripo_task_id al
      3. Gorev tamamlanana kadar polling yap
      4. GLB'yi indir -> bytes olarak don

    api_key: BYOK - Kullanicidan gelen anahtar. Bos ise TRIPO3D_API_KEY env'den okunur.
    GUVENLIK: api_key degeri kesinlikle loglanmaz.
    """
    import httpx

    # BYOK: Oncelik kullanici anahtarina, yoksa sistemin .env anahtarina
    resolved_key = (api_key or "").strip() or os.getenv("TRIPO3D_API_KEY", "").strip()
    if not resolved_key:
        raise EnvironmentError(
            "Tripo3D API anahtari bulunamadi. "
            "Arayuüzünden 'Tripo3D API Key' girin veya "
            ".env dosyasina TRIPO3D_API_KEY=<anahtariniz> ekleyin."
        )
    # GUVENLIK: Anahtari loglamiyoruz — sadece yokluk durumunu loglarız
    log.info("[Tripo3D] API anahtari %s ile calisiliyor.",
             "BYOK (kullanici)" if (api_key or "").strip() else "sistem (.env)")

    headers = {"Authorization": f"Bearer {resolved_key}"}

    # -- ADIM 1: Goruntu yukle -> image_token al
    log.info("[Tripo3D] Adim 1/3 - PNG yukleniyor...")
    push_state_fn(57, "Goruntu Tripo3D'ye yukleniyor (multipart)...")

    with httpx.Client(timeout=60) as client:
        with open(cleaned_path, "rb") as f:
            upload_resp = client.post(
                f"{_TRIPO_BASE}/upload",
                headers=headers,
                files={"file": (cleaned_path.name, f, "image/png")},
            )

    if upload_resp.status_code != 200:
        raise RuntimeError(
            f"[Tripo3D] Goruntu yukleme basarisiz: "
            f"HTTP {upload_resp.status_code} - {upload_resp.text[:300]}"
        )

    upload_data = upload_resp.json()
    if upload_data.get("code") != 0:
        raise RuntimeError(
            f"[Tripo3D] Yukleme API hatasi: {upload_data.get('message', upload_data)}"
        )

    file_token = upload_data["data"]["image_token"]
    log.info(f"[Tripo3D] image_token={file_token[:12]}...")

    # -- ADIM 2: image_to_model gorevi olustur
    log.info("[Tripo3D] Adim 2/3 - image_to_model gorevi olusturuluyor...")
    push_state_fn(62, "3D donusum gorevi baslatiliyor...")

    task_payload = {
        "type": "image_to_model",
        "file": {"type": "png", "file_token": file_token},
    }

    with httpx.Client(timeout=30) as client:
        task_resp = client.post(
            f"{_TRIPO_BASE}/task",
            headers={**headers, "Content-Type": "application/json"},
            json=task_payload,
        )

    if task_resp.status_code != 200:
        raise RuntimeError(
            f"[Tripo3D] Gorev olusturma basarisiz: "
            f"HTTP {task_resp.status_code} - {task_resp.text[:300]}"
        )

    task_data = task_resp.json()
    if task_data.get("code") != 0:
        raise RuntimeError(
            f"[Tripo3D] Gorev API hatasi: {task_data.get('message', task_data)}"
        )

    tripo_task_id = task_data["data"]["task_id"]
    log.info(f"[Tripo3D] tripo_task_id={tripo_task_id}")

    # -- ADIM 3: Polling
    log.info("[Tripo3D] Adim 3/3 - Sonuc bekleniyor...")
    elapsed = 0
    glb_url = None

    while elapsed < _POLL_TIMEOUT:
        time.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

        with httpx.Client(timeout=15) as client:
            poll_resp = client.get(
                f"{_TRIPO_BASE}/task/{tripo_task_id}",
                headers=headers,
            )

        if poll_resp.status_code != 200:
            log.warning(f"[Tripo3D] Polling HTTP {poll_resp.status_code}, tekrar deneniyor...")
            continue

        poll_data   = poll_resp.json()
        task_status = poll_data.get("data", {}).get("status", "unknown")
        progress    = poll_data.get("data", {}).get("progress", 0)

        mapped = 62 + int(progress * 0.28)   # 0-100 -> 62-90
        push_state_fn(mapped, f"[Tripo3D] Durum: {task_status} | ilerleme: %{progress}")
        log.info(f"[Tripo3D] durum={task_status}, %{progress}, {elapsed}s gecti")

        if task_status == "success":
            output  = poll_data["data"].get("output", {})
            glb_url = output.get("pbr_model") or output.get("model")
            if not glb_url:
                raise RuntimeError(
                    f"[Tripo3D] Basarili ama GLB URL bulunamadi: {output}"
                )
            log.info(f"[Tripo3D] Basarili! GLB URL: {glb_url[:60]}...")
            break

        elif task_status in ("failed", "banned", "expired", "cancelled"):
            raise RuntimeError(
                f"[Tripo3D] Gorev basarisiz. Durum: {task_status}. "
                f"Detay: {poll_data.get('data', {}).get('message', '')}"
            )

    else:
        raise TimeoutError(
            f"[Tripo3D] {_POLL_TIMEOUT}s icinde tamamlanamadi (tripo_task_id={tripo_task_id})"
        )

    # -- ADIM 4: GLB'yi indir -> bytes olarak don
    push_state_fn(92, "GLB modeli indiriliyor...")
    log.info(f"[Tripo3D] GLB indiriliyor: {glb_url}")

    with httpx.Client(timeout=120, follow_redirects=True) as client:
        dl_resp = client.get(glb_url)

    if dl_resp.status_code != 200:
        raise RuntimeError(
            f"[Tripo3D] GLB indirme basarisiz: HTTP {dl_resp.status_code}"
        )

    log.info(f"[Tripo3D] GLB indirildi ({len(dl_resp.content)/1024:.1f} KB)")
    return dl_resp.content


# ─────────────────────────────────────────────────────────────────
# Test Task (Hafta 1-2'den kalma)
# ─────────────────────────────────────────────────────────────────

@celery.task(bind=True, name="tasks.ping", max_retries=3, default_retry_delay=5)
def ping(self) -> dict:
    """Worker baglanti testi - pipeline disi kullanim."""
    logger.info(f"[Task: ping] calistı. ID: {self.request.id}")
    return {"pong": True, "task_id": self.request.id}
