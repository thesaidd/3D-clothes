"""
Kiyafet Yukleme ve Pipeline Durumu Router'i

POST /api/v1/garments/         -> Kiyafet listesi (sanal gardirop)
POST /api/v1/garments/upload   -> Fotograf al, S3'e yukle, DB kaydi olustur, Celery task tetikle
GET  /api/v1/garments/jobs/{job_id} -> Pipeline adim adim durum sorgula
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.models.garment import Garment
from app.models.schemas import (
    GarmentListResponse,
    GarmentRecord,
    GarmentUpdateRequest,
    GarmentUploadResponse,
    JobStatusResponse,
    JobStep,
)
from app.worker.celery_app import celery
from app.worker.tasks import process_garment_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/garments", tags=["garments"])

# Desteklenen formatlar ve max boyut
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB   = 15

# S3 path prefixleri
S3_ORIGINALS_PREFIX = "uploads/originals"
S3_CLEANED_PREFIX   = "uploads/cleaned"
S3_MODELS_PREFIX    = "uploads/models"


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/garments/   — Sanal Gardirop Listesi
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=GarmentListResponse,
    summary="Sanal gardirop — kayitli tum kiyafetleri listele",
)
def list_garments(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Veritabanindaki tum kiyafet kayitlarini en yeniden eskiye siralar.

    Query parametreleri:
      - limit:  Sayfa basi kayit sayisi (max 100, varsayilan 50)
      - offset: Atlanan kayit sayisi (sayfalama icin)
    """
    limit  = min(limit, 100)
    q      = db.query(Garment).order_by(Garment.created_at.desc())
    total  = q.count()
    items  = q.offset(offset).limit(limit).all()

    return GarmentListResponse(
        total=total,
        items=[
            GarmentRecord(
                id                = str(item.id),
                job_id            = item.job_id,
                garment_type      = item.garment_type,
                original_filename = item.original_filename,
                name              = item.name or "İsimsiz Kiyafet",
                is_favorite       = bool(item.is_favorite),
                status            = item.status,
                error_message     = item.error_message,
                original_url      = item.original_url,
                cleaned_url       = item.cleaned_url,
                model_url         = item.model_url,
                length_cm         = item.length_cm,
                width_cm          = item.width_cm,
                sleeve_length_cm  = item.sleeve_length_cm,
                created_at        = item.created_at,
                updated_at        = item.updated_at,
            )
            for item in items
        ],
    )


# ─────────────────────────────────────────────────────────────────
# PATCH /api/v1/garments/{garment_id}  — Ad / Favori Güncelle
# ─────────────────────────────────────────────────────────────────

@router.patch(
    "/{garment_id}",
    response_model=GarmentRecord,
    summary="Kiyafetin adini veya favori durumunu guncelle",
)
def update_garment(
    garment_id: str,
    body: GarmentUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Kismi guncelleme: `name` ve/veya `is_favorite` alanlarini degistirir.
    garment_id = Garment tablosunun UUID primary key'i.
    """
    from datetime import datetime, timezone
    garment = db.query(Garment).filter(Garment.id == garment_id).first()
    if not garment:
        raise HTTPException(status_code=404, detail=f"Kiyafet bulunamadi: {garment_id}")

    if body.name             is not None: garment.name             = body.name.strip() or "İsimsiz Kiyafet"
    if body.is_favorite      is not None: garment.is_favorite      = body.is_favorite
    if body.length_cm        is not None: garment.length_cm        = body.length_cm
    if body.width_cm         is not None: garment.width_cm         = body.width_cm
    if body.sleeve_length_cm is not None: garment.sleeve_length_cm = body.sleeve_length_cm
    garment.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(garment)
    logger.info(f"[Garment {garment_id}] Guncellendi.")

    return GarmentRecord(
        id                = str(garment.id),
        job_id            = garment.job_id,
        garment_type      = garment.garment_type,
        original_filename = garment.original_filename,
        name              = garment.name,
        is_favorite       = bool(garment.is_favorite),
        status            = garment.status,
        error_message     = garment.error_message,
        original_url      = garment.original_url,
        cleaned_url       = garment.cleaned_url,
        model_url         = garment.model_url,
        length_cm         = garment.length_cm,
        width_cm          = garment.width_cm,
        sleeve_length_cm  = garment.sleeve_length_cm,
        created_at        = garment.created_at,
        updated_at        = garment.updated_at,
    )


# ─────────────────────────────────────────────────────────────────
# DELETE /api/v1/garments/{garment_id}  — Kıyafeti Sil
# ─────────────────────────────────────────────────────────────────

@router.delete(
    "/{garment_id}",
    status_code=204,
    summary="Kiyafeti veritabanindan sil",
)
def delete_garment(
    garment_id: str,
    db: Session = Depends(get_db),
):
    """
    Kalici silme: Garment kaydini veritabanindan kaldirir.
    S3/lokal dosyalara dokunmaz (storage temizligi gelecekte).
    garment_id = UUID primary key.
    """
    garment = db.query(Garment).filter(Garment.id == garment_id).first()
    if not garment:
        raise HTTPException(status_code=404, detail=f"Kiyafet bulunamadi: {garment_id}")

    db.delete(garment)
    db.commit()
    logger.info(f"[Garment {garment_id}] Silindi (job_id={garment.job_id}).")
    # 204 No Content — response body yok


# ─────────────────────────────────────────────────────────────────
# POST /api/v1/garments/upload
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=GarmentUploadResponse,
    summary="Kiyafet fotografı yukle ve 3D pipeline'i tetikle",
    status_code=202,
)
async def upload_garment(
    file: UploadFile = File(..., description="Kiyafet fotografı (JPEG / PNG / WEBP)"),
    garment_type: str = Form(
        default="shirt",
        description="Kiyafet turu: shirt | pants | dress | jacket | skirt",
    ),
    length_cm: Optional[int] = Form(
        default=None,
        description="Kiyafet boyu (cm), opsiyonel",
    ),
    width_cm: Optional[int] = Form(
        default=None,
        description="Genislik/bel olcusu (cm), opsiyonel",
    ),
    sleeve_length_cm: Optional[int] = Form(
        default=None,
        description="Kol boyu (cm), opsiyonel",
    ),
    x_tripo_key: str = Header(
        default="",
        alias="X-Tripo-Key",
        description="BYOK: Kullanicinin kendi Tripo3D API anahtari (opsiyonel)",
        include_in_schema=True,
    ),
    db: Session = Depends(get_db),
):
    """
    Kiyafet fotografini yukler ve arka planda 3D donusturme pipeline'ini baslatir.

    - S3 tanimli ise: orijinal goruntu S3'e yuklenir.
    - S3 tanimli degilse: yerel disk fallback ile calisir.
    - Her yuklemede veritabaninda status='queued' kaydi olusturulur.

    Polling: Donen `job_id` ile `GET /api/v1/garments/jobs/{job_id}` adresini sorgulayın.
    """
    # ── 1. Validasyon ─────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Desteklenmeyen format: '{file.content_type}'. "
                f"Kabul edilenler: {sorted(ALLOWED_TYPES)}"
            ),
        )

    raw_bytes = await file.read()
    size_mb = len(raw_bytes) / (1024 * 1024)

    if size_mb > MAX_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya {size_mb:.1f} MB. Maksimum izin verilen: {MAX_SIZE_MB} MB.",
        )

    job_id = str(uuid.uuid4())
    ext    = _ext_from_content_type(file.content_type)

    # ── 2. Dosyayı S3'e veya yerel diske kaydet ───────────────────
    if settings.s3_configured:
        from app.services.storage import upload_bytes_to_s3
        s3_key    = f"{S3_ORIGINALS_PREFIX}/{job_id}{ext}"
        image_ref = upload_bytes_to_s3(
            data         = raw_bytes,
            s3_key       = s3_key,
            content_type = file.content_type,
            presigned    = False,
        )
        logger.info(f"[Job {job_id}] Orijinal S3'e yuklendi: {s3_key}")
    else:
        import aiofiles
        from pathlib import Path
        local_dir = Path("uploads/originals")
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / f"{job_id}{ext}"
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(raw_bytes)
        image_ref = str(local_path)
        logger.info(f"[Job {job_id}] S3 tanimli degil, yerel diske kaydedildi: {image_ref}")

    # ── 3. Veritabanına queued kaydı oluştur ──────────────────────
    garment = Garment(
        job_id            = job_id,
        garment_type      = garment_type,
        original_filename = file.filename,
        status            = "queued",
        original_url      = image_ref,
        length_cm         = length_cm,
        width_cm          = width_cm,
        sleeve_length_cm  = sleeve_length_cm,
    )
    db.add(garment)
    db.commit()
    logger.info(f"[Job {job_id}] DB kaydı oluşturuldu (status=queued).")

    # ── 4. Celery task'i kuyruğa ekle ────────────────────────────
    process_garment_image.apply_async(
        kwargs={
            "job_id":       job_id,
            "image_ref":    image_ref,
            "garment_type": garment_type,
            "use_s3":       settings.s3_configured,
            "api_key":      x_tripo_key or "",  # BYOK: bos ise worker .env'e fallback yapar
        },
        task_id=job_id,
    )

    logger.info(f"[Job {job_id}] Celery task kuyruğa eklendi (BYOK={'evet' if x_tripo_key else 'hayir'}).")

    return GarmentUploadResponse(
        job_id=job_id,
        status="queued",
        message=(
            f"'{file.filename}' alindi ve islem kuyruğuna eklendi. "
            "Sonuc icin job_id ile durum sorgulamasi yapin."
        ),
        estimated_time_seconds=30,
    )


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/garments/jobs/{job_id}
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Pipeline islem durumunu sorgula",
)
async def get_job_status(job_id: str):
    """
    Celery task durumunu okur ve kullaniciya adim adim ilerleme bilgisi doner.

    Celery'nin built-in FAILURE state'i result.info uzerinden okunurken
    exception_to_python() cagrisini tetikler. Bu endpoint raw backend.get_task_meta()
    ile okuma yapar — hicbir Python nesnesine deserialize etmez.

    | Celery State    | Donen status  |
    |----------------|---------------|
    | PENDING         | queued        |
    | STARTED         | processing    |
    | PROGRESS        | processing    |
    | PIPELINE_FAILED | failed        |
    | FAILURE         | failed        |
    | SUCCESS         | completed     |
    """
    from celery.result import AsyncResult

    result = AsyncResult(job_id, app=celery)

    try:
        raw          = result.backend.get_task_meta(job_id)
        celery_state = raw.get("status", "PENDING")
        raw_result   = raw.get("result", {})
    except Exception as backend_exc:
        logger.warning(f"Backend okuma hatasi job_id={job_id}: {backend_exc}")
        celery_state = "PENDING"
        raw_result   = {}

    STATE_MAP = {
        "PENDING":         "queued",
        "RECEIVED":        "queued",
        "STARTED":         "processing",
        "PROGRESS":        "processing",
        "PIPELINE_FAILED": "failed",
        "FAILURE":         "failed",
        "SUCCESS":         "completed",
        "REVOKED":         "failed",
        "RETRY":           "processing",
    }
    status = STATE_MAP.get(celery_state, "unknown")

    if celery_state in ("PIPELINE_FAILED", "PROGRESS", "STARTED", "SUCCESS"):
        meta = raw_result if isinstance(raw_result, dict) else {}
    elif celery_state == "FAILURE":
        meta = {}
        if isinstance(raw_result, dict):
            exc_type = raw_result.get("exc_type", "Error")
            exc_msg  = raw_result.get("exc_message", [])
            if isinstance(exc_msg, (list, tuple)):
                exc_msg = " ".join(str(m) for m in exc_msg)
            meta["error"] = f"{exc_type}: {exc_msg}"
        elif isinstance(raw_result, str):
            meta["error"] = raw_result
    else:
        meta = {}

    response = JobStatusResponse(
        job_id=job_id,
        status=status,
        progress=meta.get("progress", 0),
        current_step=meta.get("step", ""),
        steps=_build_steps(meta.get("steps", [])),
    )

    if status == "completed":
        response.progress            = 100
        response.original_image_path = meta.get("original_image_url") or meta.get("original_image_path")
        response.cleaned_image_path  = meta.get("cleaned_image_url")  or meta.get("cleaned_image_path")
        response.model_path          = meta.get("model_url")          or meta.get("model_path")

    if status == "failed":
        response.progress = 0
        response.error    = (
            meta.get("error") or meta.get("exc_type") or "Bilinmeyen hata"
        )

    return response


# ─────────────────────────────────────────────────────────────────
# Yardimci fonksiyonlar
# ─────────────────────────────────────────────────────────────────

def _ext_from_content_type(ct: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png":  ".png",
        "image/webp": ".webp",
    }.get(ct, ".jpg")


def _build_steps(raw: list[dict]) -> list[JobStep]:
    return [
        JobStep(
            name=s.get("name", ""),
            status=s.get("status", "pending"),
            detail=s.get("detail", ""),
        )
        for s in raw
    ]
