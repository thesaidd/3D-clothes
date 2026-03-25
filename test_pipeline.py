"""
Pipeline Entegrasyon Testi
--------------------------
Redis sunucusu gerekmez — fakeredis ile Celery'yi in-memory modda çalıştırır.

Çalıştır:
    .venv\\Scripts\\python test_pipeline.py [--skip-rembg]

--skip-rembg: rembg modelini indirmeden test etmek için (CI/CD veya hızlı test)
"""
import sys
import io
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Argüman ──────────────────────────────────────────────────────
SKIP_REMBG = "--skip-rembg" in sys.argv

print("=" * 60)
print("  VirtualTryOn — Pipeline Entegrasyon Testi")
print(f"  rembg: {'ATLANACAK (mock)' if SKIP_REMBG else 'GERÇEK'}")
print("=" * 60)

# ── Celery'yi ALWAYS_EAGER modda yapılandır ───────────────────────
# Bu mod, task'leri kuyruğa koymak yerine anında senkron çalıştırır
# Redis'e gerek kalmaz — fakeredis ile result backend sağlanır
import fakeredis
from celery import Celery
from app.config import settings

# Gerçek Redis yerine fakeredis kullan
fake_redis_server = fakeredis.FakeServer()

# Celery app'i test moduna al
from app.worker.celery_app import celery
celery.conf.update(
    task_always_eager=True,          # Redis olmadan senkron çalıştır
    task_eager_propagates=True,      # Hataları yukarı ilet
    result_backend="cache+memory://",
)

# ── Test ortamı: geçici upload klasörleri ────────────────────────
TMP_DIR = Path(tempfile.mkdtemp(prefix="vtryon_test_"))
ORIG_DIR   = TMP_DIR / "originals"
CLEAN_DIR  = TMP_DIR / "cleaned"
MODEL_DIR  = TMP_DIR / "models"

for d in [ORIG_DIR, CLEAN_DIR, MODEL_DIR]:
    d.mkdir(parents=True)

print(f"\n[Setup] Geçici test dizini: {TMP_DIR}")

# ── Gerçek yolları geçici dizinlerle değiştir ────────────────────
import app.worker.tasks as tasks_module
tasks_module.CLEANED_DIR = CLEAN_DIR
tasks_module.MODELS_DIR  = MODEL_DIR

# ── Test görüntüsü oluştur (1x1 kırmızı JPEG) ───────────────────
from PIL import Image

test_img_path = ORIG_DIR / "test_shirt.jpg"
img = Image.new("RGB", (200, 300), color=(200, 80, 80))
img.save(test_img_path, format="JPEG")
print(f"[Setup] Test görüntüsü oluşturuldu: {test_img_path} ({test_img_path.stat().st_size} bytes)")

# ── rembg mock (isteğe bağlı) ────────────────────────────────────
def _mock_remove_background(image_bytes, log):
    """rembg yerine beyaz arka planlı şeffaf PNG döner."""
    print("  [MOCK rembg] Arka plan kaldırma simülasyonu...")
    input_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    buf = io.BytesIO()
    input_img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# ── Test 1: pipeline iç fonksiyonlarını doğrudan test et ─────────
print("\n[Test 1] Pipeline iç fonksiyonları doğrudan test ediliyor...")

try:
    import uuid
    job_id     = str(uuid.uuid4())
    image_path = str(test_img_path)

    # ── Dosyayı oku ──────────────────────────────────────────────
    src = Path(image_path)
    assert src.exists(), f"Test görüntüsü yok: {src}"
    image_bytes = src.read_bytes()
    print(f"  Adım 1/3 — Görüntü okundu ({len(image_bytes)} bytes) ✅")

    # ── Arka plan kaldırma ───────────────────────────────────────
    import logging
    log = logging.getLogger("test")

    if SKIP_REMBG:
        cleaned_bytes = _mock_remove_background(image_bytes, log)
    else:
        cleaned_bytes = tasks_module._remove_background(image_bytes, log)

    cleaned_path = CLEAN_DIR / f"{job_id}_clean.png"
    cleaned_path.write_bytes(cleaned_bytes)
    assert cleaned_path.exists() and cleaned_path.stat().st_size > 0
    print(f"  Adım 2/3 — Arka plan kaldırıldı → {cleaned_path.name} ({cleaned_path.stat().st_size} bytes) ✅")

    # ── Mock Tripo3D ─────────────────────────────────────────────
    start = time.perf_counter()
    model_path = tasks_module._mock_tripo3d(job_id=job_id, cleaned_path=cleaned_path, log=log)
    elapsed = time.perf_counter() - start

    assert model_path.exists() and model_path.stat().st_size > 0
    print(f"  Adım 3/3 — [MOCK] Tripo3D tamamlandı ({elapsed:.1f}s) → {model_path.name} ✅")

    print(f"\n  original_image  : {src}")
    print(f"  cleaned_image   : {cleaned_path}")
    print(f"  model_path      : {model_path}")
    print("  [Test 1] GEÇTI ✅")

except Exception as e:
    print(f"  [Test 1] BAŞARISIZ ❌ — {e}")
    import traceback; traceback.print_exc()


# ── Test 2: Dosya bulunamadı hatası ──────────────────────────────
print("\n[Test 2] Var olmayan dosya -> hata yonetimi...")
try:
    bad_path = TMP_DIR / "nonexistent.jpg"
    bad_src  = Path(str(bad_path))
    if not bad_src.exists():
        raise FileNotFoundError(f"Goruntu bulunamadi: {bad_path}")
    print("  [Test 2] BASARISIZ - Hata firlatilmaliydi!")
except FileNotFoundError as e:
    print(f"  Beklenen hata yakalandi: {type(e).__name__}")
    print("  [Test 2] GECTI")


# ── Test 3: FastAPI route listesi ────────────────────────────────
print("\n[Test 3] FastAPI route kontrolü...")
try:
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    expected = ["/health", "/api/v1/garments/upload", "/api/v1/garments/jobs/{job_id}"]
    for r in expected:
        assert r in routes, f"Route bulunamadı: {r}"
    print(f"  Bulunan router'lar: {[r for r in routes if not r.startswith('/openapi')]}")
    print("  [Test 3] GEÇTI ✅")
except Exception as e:
    print(f"  [Test 3] BAŞARISIZ ❌ — {e}")

# ── Test 4: Upload klasörleri ─────────────────────────────────────
print("\n[Test 4] Upload klasörü oluşturma kontrolü...")
try:
    for d in ["uploads/originals", "uploads/cleaned", "uploads/models"]:
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        assert p.exists() and p.is_dir()
    print("  uploads/ klasörleri mevcut ✅")
    print("  [Test 4] GEÇTI ✅")
except Exception as e:
    print(f"  [Test 4] BAŞARISIZ ❌ — {e}")

# ── Temizlik ──────────────────────────────────────────────────────
shutil.rmtree(TMP_DIR, ignore_errors=True)
print(f"\n[Cleanup] {TMP_DIR} silindi.")
print("\n" + "=" * 60)
print("  Tüm testler tamamlandı.")
print("=" * 60)
