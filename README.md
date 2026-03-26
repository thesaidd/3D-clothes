<div align="center">

# 🪄 3D CHLOthes
## AI-Powered Virtual Fitting Room

**Kıyafetini yükle → Arka planı temizle → 3D modele dönüştür → Avatar üzerinde dene**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.x-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose)
[![AWS S3](https://img.shields.io/badge/AWS-S3-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/s3)
[![HuggingFace](https://img.shields.io/badge/🤗-IDM--VTON-FFD21E)](https://huggingface.co/yisol/IDM-VTON)

</div>

---

## 🎯 Proje Nedir?

**3D CHLOthes**, kullanıcıların kıyafet fotoğrafını yükleyerek gerçek zamanlı 3D modeline dönüştürebildiği, kişiselleştirilmiş avatar oluşturabildiği ve yapay zeka destekli sanal deneme (Virtual Try-On) yapabildiği bir **Deep Tech MVP**'dir.

Sistem uçtan uca asenkron bir pipeline üzerinde çalışır:

```
📸 Kıyafet Yükle
    └─► 🪄 Arka Plan Temizle   (rembg / isnet)
            └─► 🧊 3D Dönüştür   (Tripo3D API v2)
                    └─► 📦 Depola   (AWS S3 / yerel disk)
                            └─► 🧍 Avatar Profiline Bağla
                                    └─► 🤖 AI ile Üzerinde Dene   (IDM-VTON / HF Space)
```

---

## ✨ Özellikler

### 👗 V1 — Sanal Gardırop
- Kıyafet fotoğrafı yükleme ve anında işleme
- `rembg` ile arka plan kaldırma → temiz PNG
- **Tripo3D API v2** ile gerçek 3D GLB model üretimi
- Modeli tarayıcıda `<model-viewer>` ile 360° görüntüleme
- AWS S3 depolama (yerel disk fallback desteği)
- **BYOK:** Kendi Tripo3D API anahtarını arayüzden gir — `localStorage`'a kaydedilir, loglanmaz
- Kıyafet isimlendirme, favorileme ve silme

### 🧍 V2 — 3D Avatar Altyapısı
- Boy, kilo, cinsiyet, vücut tipi bilgileriyle avatar profili oluşturma
- Mock 3D avatar modeli ataması (`model-viewer` ile önizleme)
- Avatar listeleme ve yönetim arayüzü

### 📏 V3 — Parametrik Kıyafet Ölçüleri
- Yükleme sırasında opsiyonel ölçü girişi (boy/bel/kol boyu)
- Kıyafet kartlarında mor pill badge olarak görüntüleme
- **Sanal Kabin** — 3. sekme:
  - Avatar ve kıyafet dropdown seçimi (API'den dinamik doldurulur)
  - Canlı önizleme kartları
  - `POST /api/v1/tryon/` → **Celery** kuyruğa alır
  - `GET /api/v1/tryon/{id}` → **Polling** (her 2s) ile durum takibi
  - Sonuç görseli sağ panelde render edilir

### 🤖 V4 — Hugging Face IDM-VTON Entegrasyonu
- `gradio_client` ile **Hugging Face `yisol/IDM-VTON` Space** API çağrısı
- Avatarın cinsiyetine göre otomatik manken seçimi (Unsplash telifsiz)
- **Graceful Degradation:** API timeout/hata → fallback placeholder → `status=completed` (görev asla crash olmaz)

---

## 🏗️ Teknoloji Yığını

| Katman | Teknoloji | Görev |
|--------|-----------|-------|
| **API** | FastAPI 0.111 | REST endpoint'leri, dosya yükleme, CORS |
| **Asenkron Kuyruk** | Celery 5.x + Redis | Arka plan AI pipeline'ı |
| **Veritabanı** | PostgreSQL 15 + SQLAlchemy 2.0 | ORM, ilişkiler, durum takibi |
| **Depolama** | AWS S3 / yerel disk | Görsel + GLB model depolama |
| **3D Dönüşüm** | Tripo3D API v2 | PNG → GLB model üretimi |
| **Arka Plan** | rembg (isnet-general) | Kıyafet fotoğrafı segmentasyonu |
| **Sanal Deneme** | HF IDM-VTON + gradio_client | Kıyafeti avatar üzerinde dene |
| **3D Görüntüleme** | `<model-viewer>` (Google) | Tarayıcıda GLB render |
| **Altyapı** | Docker Compose | Tek komutla tüm servisler |
| **İzleme** | Flower | Celery task monitoring |
| **Frontend** | Vanilla HTML/CSS/JS | SPA — glassmorphism tasarım |

---

## 🚀 Kurulum

### Gereksinimler

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (v24+)
- [Git](https://git-scm.com)
- _(Opsiyonel)_ Tripo3D hesabı → [app.tripo3d.ai](https://app.tripo3d.ai)
- _(Opsiyonel)_ AWS hesabı — boş bırakılırsa yerel disk kullanılır

---

### 1️⃣ Repoyu Klonla

```bash
git clone https://github.com/thesaidd/3D-clothes.git
cd 3D-clothes
```

---

### 2️⃣ Ortam Değişkenlerini Ayarla

`.env` dosyası oluştur:

```bash
cp .env.example .env   # henüz yoksa aşağıdaki şablonu kullan
```

`.env` içeriği:

```env
# ── Tripo3D (opsiyonel — arayüzden de girilebilir) ──────────────────
TRIPO3D_API_KEY=tsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── AWS S3 (opsiyonel — boş bırakılırsa yerel disk kullanılır) ──────
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-central-1
S3_BUCKET_NAME=3d-clothes-bucket

# ── Veritabanı (Docker içinde otomatik, değiştirme) ──────────────────
DATABASE_URL=postgresql://postgres:postgres@db:5432/vtryon

# ── Redis ────────────────────────────────────────────────────────────
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

> **💡 Not:** Tripo3D anahtarı zorunlu değildir. Arayüzün sağ üstündeki **🔑 API Key** alanından istediğin zaman girebilirsin — `localStorage`'a kaydedilir ve hiçbir zaman loglanmaz.

---

### 3️⃣ Tüm Servisleri Başlat

```bash
docker compose up --build -d
```

İlk başlatmada yapılanlar:
- Python bağımlılıkları + `gradio_client` kurulur (~3-5 dk)
- `rembg` AI modeli indirilir (~100 MB)
- PostgreSQL tabloları otomatik oluşturulur (`garments`, `avatars`, `try_ons`)

---

### 4️⃣ Tarayıcıda Aç

| Servis | URL |
|--------|-----|
| 🖥️ **Ana Uygulama** | http://localhost:8000 |
| 📖 **API Docs** (Swagger) | http://localhost:8000/docs |
| 🌸 **Task Monitoring** (Flower) | http://localhost:5555 |

---

## 🔑 BYOK — Kendi API Anahtarını Kullan

### Yöntem 1: Arayüzden *(Önerilen)*
Ana sayfanın üstündeki **🔑 Tripo3D API Key** kutusuna anahtarını gir.  
Tarayıcının `localStorage`'ına kaydedilir — sayfa yenilense de kaybolmaz. Sunucu tarafında hiçbir logda görünmez.

### Yöntem 2: `.env` Dosyasından
```env
TRIPO3D_API_KEY=tsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
Kullanıcı anahtarı yoksa sistem bu anahtara otomatik fallback yapar.

---

## 📡 API Referansı

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/health` | Sistem sağlık kontrolü |
| `GET` | `/api/v1/garments/` | Gardırop listesi |
| `POST` | `/api/v1/garments/upload` | Kıyafet yükle + pipeline başlat |
| `GET` | `/api/v1/garments/jobs/{job_id}` | İşlem durumu |
| `PATCH` | `/api/v1/garments/{id}` | İsim / favori / ölçüler |
| `DELETE` | `/api/v1/garments/{id}` | Kıyafeti sil |
| `GET` | `/api/v1/avatars/` | Avatar listesi |
| `POST` | `/api/v1/avatars/` | Yeni avatar oluştur |
| `PATCH` | `/api/v1/avatars/{id}` | Avatar güncelle |
| `DELETE` | `/api/v1/avatars/{id}` | Avatar sil |
| `POST` | `/api/v1/tryon/` | Try-on işlemi başlat (async) |
| `GET` | `/api/v1/tryon/{id}` | Try-on durumu (polling) |

---

## 🗂️ Proje Yapısı

```
3D_CHLOthes/
├── app/
│   ├── main.py              # FastAPI uygulama fabrikası
│   ├── config.py            # Pydantic Settings (env yönetimi)
│   ├── db/
│   │   └── database.py      # SQLAlchemy engine + session factory
│   ├── models/
│   │   ├── garment.py       # ORM: garments   tablosu
│   │   ├── avatar.py        # ORM: avatars     tablosu
│   │   ├── tryon.py         # ORM: try_ons     tablosu
│   │   └── schemas.py       # Pydantic request/response şemaları
│   ├── routers/
│   │   ├── health.py        # GET /health
│   │   ├── garments.py      # /api/v1/garments/*
│   │   ├── avatars.py       # /api/v1/avatars/*
│   │   └── tryon.py         # /api/v1/tryon/*
│   ├── services/
│   │   └── storage.py       # S3 upload + URL yönetimi
│   └── worker/
│       ├── celery_app.py    # Celery konfigürasyonu
│       └── tasks.py         # Pipeline: rembg → Tripo3D → IDM-VTON
├── static/
│   └── index.html           # SPA — glassmorphism frontend
├── docker-compose.yml       # api + worker + db + redis + flower
├── Dockerfile               # Python image (multi-dep)
├── requirements.txt         # FastAPI, Celery, SQLAlchemy, gradio_client…
├── .env.example             # Örnek ortam değişkenleri
└── README.md
```

---

## ⚙️ Geliştirici Komutları

```bash
# Kod değişikliği sonrası yeniden başlat
docker compose restart api worker

# Tüm logları canlı izle
docker compose logs -f

# Sadece AI worker logları
docker compose logs -f worker

# Sistemi durdur
docker compose down

# Tüm verileri sıfırla (DB dahil)
docker compose down -v

# Yeni bağımlılık eklediysen image'ı yeniden build et
docker compose up --build -d
```

---

## 🗺️ Yol Haritası

| Aşama | Durum | Özellik |
|-------|-------|---------|
| **V1** | ✅ Tamamlandı | FastAPI + Celery + rembg + Tripo3D + S3 + Gardırop |
| **V2** | ✅ Tamamlandı | Avatar profili (boy/kilo/cinsiyet) + 3D model viewer |
| **V3** | ✅ Tamamlandı | Parametrik ölçüler + Sanal Kabin arayüzü + Async TryOn |
| **V4** | ✅ Tamamlandı | HF IDM-VTON + gradio_client + Graceful Degradation |
| **V5** | 🔲 Planlandı | NSFW filtresi (NudeNet) |
| **V6** | 🔲 Planlandı | JWT kimlik doğrulama + kullanıcı geçmişi |
| **V7** | 🔲 Planlandı | S3'e HF sonucu yükleme + kalıcı URL |

---

## 📄 Lisans

MIT License — Detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

<div align="center">
<strong>🚀 Sevgiyle inşa edildi</strong><br>
FastAPI × Celery × PostgreSQL × Tripo3D × HuggingFace IDM-VTON × AWS S3
</div>
