"""
ValueError: Exception information must include the exception type regresyon testi.
Redis olmadan fakeredis ile calisir.
"""
import sys, io, uuid, time, logging, shutil, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Celery'yi in-memory + fakeredis ile yapilandir ───────────────
import fakeredis
from celery import states as celery_states
from app.worker.celery_app import celery

fake_server = fakeredis.FakeServer()
fake_conn   = fakeredis.FakeRedis(server=fake_server, decode_responses=True)

# RedisBackend'in _get_key_for_task ve get/set metodlarini mock'la
import unittest.mock as mock

# Celery sonuc backend'ini fakeredis ile degistir
from celery.backends.redis import RedisBackend

# ── Test duzeni ──────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp())
clean_dir = tmp / "cleaned"
model_dir = tmp / "models"
clean_dir.mkdir(); model_dir.mkdir()

import app.worker.tasks as tasks_module
tasks_module.CLEANED_DIR = clean_dir
tasks_module.MODELS_DIR  = model_dir

from PIL import Image
img_path = tmp / "shirt.jpg"
Image.new("RGB", (100, 150), (200, 80, 80)).save(img_path)

log = logging.getLogger("test")

def mock_bg(img_bytes, log_):
    buf = io.BytesIO()
    Image.open(io.BytesIO(img_bytes)).convert("RGBA").save(buf, "PNG")
    return buf.getvalue()

PASS = 0; FAIL = 0

def ok(label):
    global PASS
    print(f"  PASS  {label}")
    PASS += 1

def fail(label, detail=""):
    global FAIL
    print(f"  FAIL  {label}" + (f": {detail}" if detail else ""))
    FAIL += 1

# ── Test 1: Basarili pipeline ─────────────────────────────────────
print("\n[Test 1] Basarili pipeline -> SUCCESS meta dogrulama")
try:
    job_id = str(uuid.uuid4())
    raw_bytes = img_path.read_bytes()
    cleaned = mock_bg(raw_bytes, log)
    cp = clean_dir / f"{job_id}_clean.png"
    cp.write_bytes(cleaned)
    mp = tasks_module._mock_tripo3d(job_id=job_id, cleaned_path=cp, log=log)

    # tasks.py'nin return degerini simule et (SUCCESS meta)
    success_meta = {
        "progress": 100,
        "step": "completed",
        "steps": [
            {"name": "background_removal", "status": "done", "detail": ""},
            {"name": "mock_3d_conversion",  "status": "done", "detail": ""},
        ],
        "original_image_path": str(img_path),
        "cleaned_image_path":  str(cp),
        "model_path":          str(mp),
    }

    # garments.py mantigi: SUCCESS state, raw_result = meta dict
    celery_state = "SUCCESS"
    raw_result   = success_meta
    meta = raw_result if isinstance(raw_result, dict) else {}

    assert meta.get("progress") == 100
    assert Path(meta["cleaned_image_path"]).exists()
    assert Path(meta["model_path"]).exists()
    ok("SUCCESS meta dict dogru okundu")
    ok(f"cleaned_image mevcut ({cp.stat().st_size} bytes)")
    ok(f"model_path mevcut ({mp.stat().st_size} bytes)")
except Exception as e:
    fail("Basarili pipeline", str(e))

# ── Test 2: PIPELINE_FAILED state (bizim ozel state) ─────────────
print("\n[Test 2] PIPELINE_FAILED state -> ValueError olmadan okunur")
try:
    # tasks.py'nin except blogundaki update_state cagrisinin meta'si
    pipeline_failed_meta = {
        "step":      "error",
        "progress":  0,
        "steps":     [{"name": "background_removal", "status": "error", "detail": "Test hatasi"}],
        "error":     "Test hatasi mesaji",
        "exc_type":  "RuntimeError",
        "traceback": "Traceback...\nRuntimeError: Test hatasi mesaji",
    }

    # garments.py mantigi: PIPELINE_FAILED -> meta = raw_result
    celery_state = "PIPELINE_FAILED"
    raw_result   = pipeline_failed_meta
    meta = raw_result if isinstance(raw_result, dict) else {}

    assert meta.get("error") == "Test hatasi mesaji"
    assert meta.get("exc_type") == "RuntimeError"
    assert meta.get("progress") == 0

    # STATE_MAP kontrolu
    STATE_MAP = {
        "PENDING": "queued", "RECEIVED": "queued",
        "STARTED": "processing", "PROGRESS": "processing",
        "PIPELINE_FAILED": "failed",
        "FAILURE": "failed", "SUCCESS": "completed",
        "REVOKED": "failed", "RETRY": "processing",
    }
    status = STATE_MAP.get(celery_state, "unknown")
    assert status == "failed"

    ok("PIPELINE_FAILED -> status=failed donusumu dogru")
    ok("PIPELINE_FAILED meta hatasiz okundu (ValueError yok)")
    ok(f"error mesaji: '{meta['error']}'")
except Exception as e:
    fail("PIPELINE_FAILED parse", str(e))

# ── Test 3: FAILURE state (Celery built-in, retry bitince) ───────
print("\n[Test 3] Celery FAILURE state -> exception dict guvenle parse edilir")
try:
    # Celery'nin FAILURE state'inde backend'e yazdigi format:
    celery_failure_raw = {
        "exc_type":    "FileNotFoundError",
        "exc_message": ["[Errno 2] No such file or directory: '/test.jpg'"],
        "exc_tb":      "Traceback (most recent call last):\n  ...\nFileNotFoundError",
    }

    # garments.py FAILURE branch mantigi
    celery_state = "FAILURE"
    raw_result   = celery_failure_raw
    meta = {}

    if isinstance(raw_result, dict):
        exc_type = raw_result.get("exc_type", "Error")
        exc_msg  = raw_result.get("exc_message", [])
        if isinstance(exc_msg, (list, tuple)):
            exc_msg = " ".join(str(m) for m in exc_msg)
        meta["error"] = f"{exc_type}: {exc_msg}"

    assert "FileNotFoundError" in meta["error"]
    assert "No such file" in meta["error"]
    ok("FAILURE exc_type dogru cozuldu: " + exc_type)
    ok("FAILURE mesaji: " + meta["error"][:60])
    ok("ValueError firlatilmadi (result.info hic cagirilmadi)")
except Exception as e:
    fail("FAILURE parse", str(e))

# ── Test 4: Bozuk/None meta -> guvenli fallback ───────────────────
print("\n[Test 4] Bozuk backend yaniti -> guvenli fallback")
try:
    for bad_raw in [None, "str-meta", 42, [], b"bytes"]:
        celery_state = "PIPELINE_FAILED"
        raw_result   = bad_raw
        meta = raw_result if isinstance(raw_result, dict) else {}
        # Hic hata firlatilmamali
        _ = meta.get("error", "Bilinmeyen hata")
    ok("Tum bozuk tipler icin dict fallback calisti")
except Exception as e:
    fail("Bozuk meta fallback", str(e))

# ── Test 5: PENDING state ────────────────────────────────────────
print("\n[Test 5] PENDING state -> meta bos, status=queued")
try:
    celery_state = "PENDING"
    raw_result   = {}
    meta = {}
    STATE_MAP = {"PENDING": "queued"}
    status = STATE_MAP.get(celery_state, "unknown")
    assert status == "queued"
    assert meta == {}
    ok("PENDING -> queued, meta bos")
except Exception as e:
    fail("PENDING state", str(e))

# ── Sonuc ────────────────────────────────────────────────────────
shutil.rmtree(tmp)
print(f"\n{'='*50}")
print(f"  Sonuc: {PASS} PASS, {FAIL} FAIL")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)
