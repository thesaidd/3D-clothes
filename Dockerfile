FROM python:3.11-slim

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Bağımlılıkları önce kopyala (Docker layer cache optimizasyonu)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kaynak kodunu kopyala
COPY ./app ./app

# Frontend static dosyalarini kopyala
# (Volume mount yoksa da image icinde calismasi icin)
COPY ./static ./static

# Upload dizinlerini onceden olustur (StaticFiles mount icin gerekli)
RUN mkdir -p uploads/originals uploads/cleaned uploads/models

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
