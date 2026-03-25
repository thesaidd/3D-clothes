import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="3D Virtual Try-On — MVP Backend",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rotalar ────────────────────────────────────────────────────
    from app.routers import health, garments
    app.include_router(health.router)
    app.include_router(garments.router)

    # Aşağıdaki router'lar ilerleyen haftalarda eklenir:
    # from app.routers import avatars
    # app.include_router(avatars.router)

    # ── Upload & Static Klasörleri ──────────────────────────────────
    # app.mount() çağrısı anında dizin yoksa FastAPI RuntimeError fırlatır.
    # on_startup async event'i mount'tan SONRA çalışır, bu yüzden
    # klasörleri burada — mount'tan ÖNCE — senkron olarak oluşturuyoruz.
    from pathlib import Path

    _upload_dirs = [
        Path("uploads"),
        Path("uploads/originals"),
        Path("uploads/cleaned"),
        Path("uploads/models"),
        Path("static"),           # mount için static/ de mevcut olmalı
    ]
    for _d in _upload_dirs:
        _d.mkdir(parents=True, exist_ok=True)

    logger.info("Upload ve static klasörleri hazırlandı.")

    # ── Static Mount ────────────────────────────────────────────────
    # Yüklenen dosyaları (/uploads/cleaned/... vb.) tarayıcıya sun
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    # Frontend HTML'ini kök dizinde sun (index.html → localhost:8000/)
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

    @app.on_event("startup")
    async def on_startup():
        # ── Tablolari olustur (mevcut tablolar atlanir) ──────────
        # Import sirasi onemli: model dosyalari Base'e kayit olsun
        from app.db.database import Base, engine
        import app.models.garment  # noqa: F401 — modeli Base'e kayit eder

        Base.metadata.create_all(bind=engine)
        logger.info("Veritabani tablolari kontrol edildi / olusturuldu.")
        logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} baslatildi.")

    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("Uygulama kapatiliyor...")

    return app


app = create_app()
