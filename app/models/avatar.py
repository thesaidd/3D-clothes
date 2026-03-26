"""
Avatar ORM modeli — Kullanicinin vücut ölçülerini saklar.

Alanlar:
    id            UUID primary key
    name          Kullanicinin verdigi isim (orn. "Benim Avatarım")
    gender        male | female | unisex
    height_cm     Boy (santimetre)
    weight_kg     Agirlik (kilogram)
    body_shape    rectangle | triangle | hourglass | inverted_triangle | oval
    model_url     Uretilecek 3D GLB modelin S3 URL'si (henüz null)
    created_at    Kayit tarihi (UTC)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class Avatar(Base):
    __tablename__ = "avatars"

    # ── Kimlik ────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )

    # ── Temel Bilgiler ────────────────────────────────────────────
    name = Column(
        String(200),
        nullable=False,
        default="Benim Avatarım",
        comment="Kullanicinin verdigi avatar adi",
    )

    gender = Column(
        String(20),
        nullable=False,
        comment="male | female | unisex",
    )

    # ── Vücut Ölçüleri ────────────────────────────────────────────
    height_cm = Column(
        Integer,
        nullable=False,
        comment="Boy (santimetre)",
    )

    weight_kg = Column(
        Integer,
        nullable=False,
        comment="Agirlik (kilogram)",
    )

    body_shape = Column(
        String(30),
        nullable=False,
        comment="rectangle | triangle | hourglass | inverted_triangle | oval",
    )

    # ── 3D Model ──────────────────────────────────────────────────
    model_url = Column(
        String(1024),
        nullable=True,
        comment="Uretilen 3D GLB modelinin S3/lokal URL'si (henuz bos)",
    )

    # ── Zaman Damgasi ─────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Kayit zamani (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<Avatar id={self.id!r} name={self.name!r} "
            f"gender={self.gender} {self.height_cm}cm/{self.weight_kg}kg>"
        )
