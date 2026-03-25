from pydantic import BaseModel, Field
from typing import Optional
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
