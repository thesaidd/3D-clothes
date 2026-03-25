"""
Tripo3D API Key Dogrulama & Canli Entegrasyon Testi
----------------------------------------------------
Kullanim:
    .venv\\Scripts\\python test_tripo_live.py

Yapilan islemler:
  1. .env'den TRIPO3D_API_KEY'i oku
  2. GET /task endpointine istek at -> API key gecerli mi?
  3. Kucuk bir test PNG'si olustur -> _call_tripo3d() ile gercek API'ye gonder
  4. GLB dosyasini indir ve diskte kontrol et
"""
import os
import sys
import io
import uuid
import shutil
import tempfile
import time
from pathlib import Path

# .env'i yukle (dotenv varsa, yoksa os.environ'a geri don)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[Setup] .env dosyasi yuklendi (python-dotenv)")
except ImportError:
    # Manuel okuma
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        print("[Setup] .env dosyasi manuel okundu")
    else:
        print("[Setup] UYARI: .env dosyasi bulunamadi")

import httpx

api_key = os.getenv("TRIPO3D_API_KEY", "").strip()
if not api_key:
    print("\nHATA: TRIPO3D_API_KEY env degiskeni bos veya tanimlanmamis.")
    print("      .env dosyasina  TRIPO3D_API_KEY=tpio_xxxx  satirini ekleyin.")
    sys.exit(1)

print(f"\n[1] API key okundu: {api_key[:8]}...{api_key[-4:]}")

TRIPO_BASE = "https://api.tripo3d.ai/v2/openapi"
headers    = {"Authorization": f"Bearer {api_key}"}

# ── TEST 1: API key gecerliligi (bakiye sorgula) ─────────────────
print("\n[2] API key dogrulanıyor (GET /user/balance)...")
try:
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{TRIPO_BASE}/user/balance", headers=headers)

    if r.status_code == 200 and r.json().get("code") == 0:
        balance = r.json().get("data", {})
        print(f"    API key GECERLI. Bakiye bilgisi: {balance}")
    elif r.status_code == 401:
        print("    HATA: API key gecersiz veya suresi dolmus (HTTP 401).")
        sys.exit(1)
    else:
        # Bazi planlarda bu endpoint olmayabilir, devam et
        print(f"    Uyari: status={r.status_code}, {r.text[:100]}")
        print("    (balance endpoint desteklenmeyebilir; upload testine devam ediliyor)")
except Exception as e:
    print(f"    Baglanti hatasi: {e}")
    sys.exit(1)

# ── TEST 2: Gercek upload + image_to_model + polling + GLB indir ─
print("\n[3] Gercek pipeline testi basliyor...")
print("    Kucuk bir test PNG olusturuluyor...")

from PIL import Image

tmp      = Path(tempfile.mkdtemp(prefix="tripo_test_"))
img_path = tmp / "test_shirt_clean.png"
# 256x256 seffaf PNG (rembg çıktısını simule eder)
img = Image.new("RGBA", (256, 256), (220, 100, 80, 255))
# Ortaya beyaz dikdortgen (kiyafet gibi)
for x in range(60, 196):
    for y in range(40, 216):
        img.putpixel((x, y), (255, 255, 255, 255))
img.save(img_path, format="PNG")
print(f"    Test PNG olusturuldu: {img_path} ({img_path.stat().st_size} bytes)")

# Task modülünden gercek fonksiyonu import et
sys.path.insert(0, ".")
from app.worker.tasks import _call_tripo3d, MODELS_DIR

# Geçici model dizini
test_models_dir = tmp / "models"
test_models_dir.mkdir()

# _call_tripo3d patch'le: MODELS_DIR yerine gecici klasoru kullan
import app.worker.tasks as tasks_module
original_models_dir = tasks_module.MODELS_DIR
tasks_module.MODELS_DIR = test_models_dir

job_id = str(uuid.uuid4())
log    = __import__("logging").getLogger("tripo_test")

progress_log = []
def push_fn(progress, detail):
    progress_log.append((progress, detail))
    print(f"    [{progress:3d}%] {detail}")

print(f"\n[4] _call_tripo3d() cagirılıyor (job_id={job_id[:8]}...)...")
print("    (Bu islem 1-5 dakika surebilir — gercek API cagrisı yapılıyor)\n")

start = time.perf_counter()
try:
    model_path = _call_tripo3d(
        job_id=job_id,
        cleaned_path=img_path,
        log=log,
        push_state_fn=push_fn,
    )
    elapsed = time.perf_counter() - start

    print(f"\n[BASARILI] Toplam sure: {elapsed:.1f}s")
    print(f"  GLB yolu  : {model_path}")
    print(f"  GLB boyutu: {model_path.stat().st_size / 1024:.1f} KB")
    assert model_path.exists() and model_path.stat().st_size > 1000, \
        "GLB dosyasi bos veya cok kucuk!"
    print("  Boyut kontrolu: GECTI (>1 KB)")

except EnvironmentError as e:
    print(f"\nCevre hatasi: {e}")
    sys.exit(1)
except Exception as e:
    elapsed = time.perf_counter() - start
    print(f"\n[HATA] {elapsed:.1f}s sonra hata: {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)
finally:
    tasks_module.MODELS_DIR = original_models_dir
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n[Temizlik] {tmp} silindi.")

print("\n" + "="*50)
print("  TRIPO3D ENTEGRASYON TESTI: TAMAMLANDI")
print("="*50)
