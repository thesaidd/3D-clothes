"""
app/models/tryon.py
-------------------
TryOn SQLAlchemy modeli — sanal deneme islemlerini temsil eder.

Tablo: try_ons
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class TryOn(Base):
    __tablename__ = "try_ons"

    # ── Birincil Anahtar ──────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        comment="Birincil anahtar (UUID)",
    )

    # ── İlişkiler ─────────────────────────────────────────────────
    avatar_id = Column(
        UUID(as_uuid=True),
        ForeignKey("avatars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Bağlı avatar kaydının UUID'si",
    )

    garment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("garments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Bağlı kıyafet kaydının UUID'si",
    )

    # ── İşlem Durumu ──────────────────────────────────────────────
    status = Column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | processing | completed | failed",
    )

    error_message = Column(
        Text,
        nullable=True,
        comment="Hata mesajı (status=failed olduğunda dolar)",
    )

    # ── Sonuç ─────────────────────────────────────────────────────
    result_url = Column(
        Text,
        nullable=True,
        comment="Try-on sonucu görsel URL'si (S3 veya placeholder)",
    )

    # ── Zaman Damgası ─────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Kaydın oluşturulduğu zaman (UTC)",
    )

    def __repr__(self) -> str:
        return (
            f"<TryOn id={self.id} avatar={self.avatar_id} "
            f"garment={self.garment_id} status={self.status!r}>"
        )
