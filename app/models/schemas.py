from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


# ── Upload ────────────────────────────────────────────────────────

class GarmentUploadResponse(BaseModel):
    job_id: str = Field(..., description="İşlemi takip etmek için kullanın")
    status: str = Field(..., description="queued | processing | completed | failed")
    message: str
    estimated_time_seconds: int = Field(default=30)


# ── Job Status ────────────────────────────────────────────────────

class JobStep(BaseModel):
    name: str
    status: str   # pending | running | done | error
    detail: str = ""


class JobStatusResponse(BaseModel):
    job_id: str
    status: str                          # queued | processing | completed | failed
    progress: int = Field(0, ge=0, le=100)
    current_step: str = ""
    steps: list[JobStep] = []

    # Tamamlandığında dolar
    original_image_path: Optional[str] = None
    cleaned_image_path: Optional[str] = None
    model_path: Optional[str] = None

    error: Optional[str] = None


# ── Sanal Gardirop ────────────────────────────────────────────────

class GarmentRecord(BaseModel):
    """Tek bir kiyafet kaydini temsil eder (DB satirindan donusum)."""
    id: str
    job_id: str
    garment_type: str
    original_filename: Optional[str] = None
    name: str = "İsimsiz Kıyafet"
    is_favorite: bool = False
    status: str
    error_message: Optional[str] = None
    original_url: Optional[str] = None
    cleaned_url: Optional[str] = None
    model_url: Optional[str] = None
    # Fiziksel olculer
    length_cm: Optional[int] = None
    width_cm: Optional[int] = None
    sleeve_length_cm: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True   # SQLAlchemy ORM nesnelerinden okuma icin


class GarmentListResponse(BaseModel):
    total: int
    items: list[GarmentRecord]


class GarmentUpdateRequest(BaseModel):
    """PATCH /garments/{id} — Kismi guncelleme."""
    name: Optional[str] = Field(None, max_length=200, description="Kiyafetin ozel adi")
    is_favorite: Optional[bool] = Field(None, description="Favori durumu")
    # Fiziksel olculer
    length_cm: Optional[int] = Field(None, ge=1, le=500, description="Kiyafet boyu (cm)")
    width_cm: Optional[int] = Field(None, ge=1, le=300, description="Genislik/bel (cm)")
    sleeve_length_cm: Optional[int] = Field(None, ge=1, le=200, description="Kol boyu (cm)")


# ── Avatar ────────────────────────────────────────────────────────

GenderType    = Literal["male", "female", "unisex"]
BodyShapeType = Literal["rectangle", "triangle", "hourglass", "inverted_triangle", "oval"]


class AvatarCreate(BaseModel):
    """POST /api/v1/avatars/ — Yeni avatar olustur."""
    name: str = Field("Benim Avatarım", max_length=200, description="Avatar adi")
    gender: GenderType = Field(..., description="male | female | unisex")
    height_cm: int = Field(..., ge=50, le=250, description="Boy (cm)")
    weight_kg: int = Field(..., ge=20, le=300, description="Agirlik (kg)")
    body_shape: BodyShapeType = Field(
        ..., description="rectangle | triangle | hourglass | inverted_triangle | oval"
    )


class AvatarUpdate(BaseModel):
    """PATCH /api/v1/avatars/{id} — Kismi guncelleme."""
    name: Optional[str] = Field(None, max_length=200)
    gender: Optional[GenderType] = None
    height_cm: Optional[int] = Field(None, ge=50, le=250)
    weight_kg: Optional[int] = Field(None, ge=20, le=300)
    body_shape: Optional[BodyShapeType] = None
    model_url: Optional[str] = None   # 3D GLB asset URL'si (mock veya gercek)


class AvatarResponse(BaseModel):
    """Tek bir avatar kaydini temsil eder."""
    id: str
    name: str
    gender: str
    height_cm: int
    weight_kg: int
    body_shape: str
    model_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AvatarListResponse(BaseModel):
    total: int
    items: list[AvatarResponse]


# ── TryOn ─────────────────────────────────────────────────────────

class TryOnCreate(BaseModel):
    """POST /api/v1/tryon/ — Yeni try-on işlemi başlat."""
    avatar_id: str = Field(..., description="Avatar UUID")
    garment_id: str = Field(..., description="Garment UUID")


class TryOnResponse(BaseModel):
    """Try-on kaydının güncel durumunu temsil eder."""
    id: str
    avatar_id: str
    garment_id: str
    status: str                    # pending | processing | completed | failed
    result_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
