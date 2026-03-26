"""
app/models/garment.py
---------------------
Garment SQLAlchemy modeli — kiyafet kayitlarini temsil eder.

Tablo: garments
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class Garment(Base):
    __tablename__ = "garments"

    # ── Birincil Anahtar ──────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Birincil anahtar (UUID)",
    )

    # ── Celery ile Esleme ─────────────────────────────────────────
    job_id = Column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
        comment="Celery task ID ile eslesen benzersiz is kimlik",
    )

    # ── Kiyafet Bilgileri ─────────────────────────────────────────
    garment_type = Column(
        String(50),
        nullable=False,
        default="shirt",
        comment="shirt | pants | dress | jacket | skirt",
    )

    original_filename = Column(
        String(255),
        nullable=True,
        comment="Kullanicinin yukledigi orijinal dosya adi",
    )

    name = Column(
        String(200),
        nullable=False,
        default="İsimsiz Kiyafet",
        comment="Kullanicinin verdigi ozel isim",
    )

    is_favorite = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Favori olarak isaretlendi mi?",
    )

    # ── Islem Durumu ──────────────────────────────────────────────
    status = Column(
        String(30),
        nullable=False,
        default="queued",
        index=True,
        comment="queued | processing | completed | failed",
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Hata mesaji (status=failed oldugunda dolar)",
    )

    # ── Dosya URL'leri (S3 veya yerel yol) ───────────────────────
    original_url = Column(
        Text,
        nullable=True,
        comment="Orijinal fotografin S3 URL'si veya yerel yolu",
    )

    cleaned_url = Column(
        Text,
        nullable=True,
        comment="Arka plani temizlenmis PNG'nin URL'si",
    )

    model_url = Column(
        Text,
        nullable=True,
        comment="Uretilen 3D GLB modelinin URL'si",
    )

    # ── Fiziksel Ölçüler (opsiyonel) ──────────────────────────
    length_cm = Column(
        Integer,
        nullable=True,
        comment="Kiyafetin boyu (cm) — opsiyonel",
    )

    width_cm = Column(
        Integer,
        nullable=True,
        comment="Kiyafetin genisligi / bel olcusu (cm) — opsiyonel",
    )

    sleeve_length_cm = Column(
        Integer,
        nullable=True,
        comment="Kol boyu (cm) — opsiyonel",
    )

    # ── Zaman Damgalari ───────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Kaydin olusturuldugu zaman (UTC)",
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Son guncelleme zamani (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<Garment id={self.id} job_id={self.job_id!r} "
            f"status={self.status!r} type={self.garment_type!r}>"
        )
