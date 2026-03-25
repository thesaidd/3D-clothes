<div align="center">

# 👕 3D Virtual Try-On

**Fotoğrafını çek → Arka planı temizle → 3D modele dönüştür → Sanal gardıroba ekle**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.x-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-316192?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose)
[![AWS S3](https://img.shields.io/badge/AWS-S3-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/s3)

</div>

---

## 🎯 Proje Nedir?

**3D Virtual Try-On**, kullanıcıların kıyafet fotoğrafını yükleyerek gerçek zamanlı 3D modeline dönüştürebildiği ve sanal gardırobunda yönetilebileceği bir **Deep Tech MVP**'dir.

Pipeline tek bir tıkla çalışır:

```
📸 Fotoğraf Yükleme
    └─► 🪄 Arka Plan Temizleme  (rembg / isnet)
            └─► 🧊 3D Dönüşüm  (Tripo3D API v2)
                    └─► 📦 Depolama  (AWS S3 veya yerel disk)
                            └─► 🖥️ Tarayıcıda Görüntüleme  (<model-viewer>)
```

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
│                                                                 │
│  ┌──────────┐   HTTP    ┌──────────┐   Task    ┌────────────┐  │
│  │ Browser  │──────────►│ FastAPI  │──────────►│   Celery   │  │
│  │ (HTML/JS)│           │  :8000   │           │   Worker   │  │
│  └──────────┘           └────┬─────┘           └─────┬──────┘  │
│                              │                       │          │
│                         ┌────▼─────┐          ┌─────▼──────┐  │
│                         │PostgreSQL│          │   Redis    │  │
│                         │  :5432   │          │   :6379    │  │
│                         └──────────┘          └────────────┘  │
│                                                                 │
│  🌐 Tripo3D API v2  ←──── Worker              ────► 🪣 AWS S3  │
└─────────────────────────────────────────────────────────────────┘
```

| Katman | Teknoloji | Görev |
|--------|-----------|-------|
| **API** | FastAPI | REST endpoint'leri, dosya yükleme, CORS |
| **Kuyruk** | Celery + Redis | Asenkron 3D dönüşüm pipeline'ı |
| **Veritabanı** | PostgreSQL + SQLAlchemy | Kıyafet kayıtları, durum takibi |
| **Depolama** | AWS S3 (veya yerel disk) | Görsel ve GLB model depolama |
| **3D AI** | Tripo3D API v2 | PNG'den GLB model üretimi |
| **Arka Plan** | rembg (isnet) | Kıyafet fotoğrafı segmentasyonu |
| **Frontend** | Vanilla HTML/CSS/JS | Tek sayfa uygulama + `<model-viewer>` |
| **İzleme** | Flower | Celery task monitoring (:5555) |

---

## 🚀 Kurulum

### Gereksinimler

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (v24+)
- [Git](https://git-scm.com)
- Tripo3D hesabı → [app.tripo3d.ai](https://app.tripo3d.ai) (isteğe bağlı)
- AWS hesabı (isteğe bağlı — yerel disk fallback mevcut)

### 1️⃣ Repoyu klonla

```bash
git clone https://github.com/KULLANICI_ADI/3D_CHLOthes.git
cd 3D_CHLOthes
```

### 2️⃣ Ortam değişkenlerini ayarla

```bash
cp .env.example .env
```

`.env` dosyasını düzenle:

```env
# Tripo3D (isteğe bağlı — arayüzden de girilebilir)
TRIPO3D_API_KEY=tsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# AWS S3 (isteğe bağlı — boş bırakılırsa yerel disk kullanılır)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-central-1
S3_BUCKET_NAME=my-vtryon-bucket

# Veritabanı (Docker'da otomatik, değiştirme)
DATABASE_URL=postgresql://postgres:postgres@db:5432/vtryon
```

### 3️⃣ Başlat

```bash
docker compose up --build -d
```

İlk başlatmada:
- Python bağımlılıkları kurulur (~2-3 dk)
- `rembg` modeli indirilir (~100 MB)
- PostgreSQL tabloları otomatik oluşturulur

### 4️⃣ Tarayıcıda aç

| Servis | URL |
|--------|-----|
| 🖥️ Ana uygulama | http://localhost:8000 |
| 📖 API dokümantasyonu | http://localhost:8000/docs |
| 🌸 Task monitoring (Flower) | http://localhost:5555 |

---

## 🔑 BYOK — Kendi API Anahtarını Kullan

Bu projeyi fork'ladığında Tripo3D anahtarın olmayabilir. Sistemi kendi anahtarınla çalıştırmanın iki yolu var:

### Yöntem 1: Arayüzden (Önerilen)
Ana sayfanın üst kısmındaki **🔑 Tripo3D API Key** alanına anahtarını gir. Tarayıcının `localStorage`'ına kaydedilir — sayfa yenilemende kaybolmaz. Anahtar hiçbir zaman server-side loglanmaz.

### Yöntem 2: `.env` dosyasından
```env
TRIPO3D_API_KEY=tsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
Sistem, kullanıcıdan gelen anahtar yoksa otomatik olarak bu anahtara fallback yapar.

---

## 📡 API Referansı

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/` | Ana uygulama (HTML) |
| `GET` | `/health` | Sağlık kontrolü |
| `GET` | `/api/v1/garments/` | Gardırop listesi |
| `POST` | `/api/v1/garments/upload` | Kıyafet yükle + pipeline başlat |
| `GET` | `/api/v1/garments/jobs/{job_id}` | İşlem durumunu sorgula |
| `PATCH` | `/api/v1/garments/{id}` | İsim / favori güncelle |
| `DELETE` | `/api/v1/garments/{id}` | Kıyafeti sil |

### Upload — Header

```http
POST /api/v1/garments/upload
Content-Type: multipart/form-data
X-Tripo-Key: tsk_xxx     ← BYOK (isteğe bağlı)
```

---

## 🗂️ Proje Yapısı

```
3D_CHLOthes/
├── app/
│   ├── main.py              # FastAPI uygulama fabrikası
│   ├── config.py            # Pydantic Settings (env yönetimi)
│   ├── db/
│   │   └── database.py      # SQLAlchemy engine + session
│   ├── models/
│   │   ├── garment.py       # ORM modeli (garments tablosu)
│   │   └── schemas.py       # Pydantic response şemaları
│   ├── routers/
│   │   └── garments.py      # Tüm /garments endpoint'leri
│   ├── services/
│   │   └── storage.py       # S3 upload / URL yönetimi
│   └── worker/
│       ├── celery_app.py    # Celery konfigürasyonu
│       └── tasks.py         # Pipeline: rembg → Tripo3D → kaydet
├── static/
│   └── index.html           # Tek sayfa frontend (BYOK + Gardırop)
├── docker-compose.yml       # api + worker + db + redis + flower
├── Dockerfile               # Multi-stage Python image
├── requirements.txt
├── .env.example             # Örnek ortam değişkenleri
└── README.md
```

---

## ⚙️ Geliştirme

```bash
# Servisleri yeniden başlat (kod değişikliğinde)
docker compose restart api worker

# Tüm logları izle
docker compose logs -f

# Sadece worker logları
docker compose logs -f worker

# Sistemi durdur
docker compose down

# Tüm verileri sil (DB dahil)
docker compose down -v
```

---

## 🔮 Yol Haritası

- [x] FastAPI + Celery asenkron pipeline
- [x] rembg ile arka plan temizleme
- [x] Tripo3D API v2 entegrasyonu
- [x] AWS S3 depolama (yerel disk fallback)
- [x] PostgreSQL veritabanı + SQLAlchemy ORM
- [x] Sanal gardırop (isim, favori, silme)
- [x] BYOK (Bring Your Own Key)
- [ ] NSFW filtresi (NudeNet)
- [ ] ReadyPlayerMe avatar entegrasyonu
- [ ] IDM-VTON ile kıyafet deneme
- [ ] Kullanıcı kimlik doğrulama (JWT)

---

## 📄 Lisans

MIT License — Detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

<div align="center">
<strong>🚀 Sevgiyle inşa edildi · FastAPI × Celery × Tripo3D × AWS</strong>
</div>
