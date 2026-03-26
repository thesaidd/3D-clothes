"""
app/routers/tryon.py
--------------------
POST /api/v1/tryon/       — Try-on işlemi başlat (Celery async)
GET  /api/v1/tryon/{id}   — İşlem durumunu sorgula (polling)
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.tryon import TryOn
from app.models.schemas import TryOnCreate, TryOnResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tryon", tags=["tryon"])


# ─────────────────────────────────────────────────────────────────
# POST /api/v1/tryon/  — İşlemi Başlat
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=TryOnResponse,
    status_code=202,
    summary="Sanal deneme işlemini başlat",
)
def create_tryon(body: TryOnCreate, db: Session = Depends(get_db)):
    """
    Yeni bir try-on kaydı oluşturur (status=pending) ve
    Celery worker'ına process_tryon_task görevi gönderir.
    """
    tryon = TryOn(
        avatar_id  = uuid.UUID(body.avatar_id),
        garment_id = uuid.UUID(body.garment_id),
        status     = "pending",
    )
    db.add(tryon)
    db.commit()
    db.refresh(tryon)
    logger.info(f"[TryOn {tryon.id}] Olusturuldu (pending).")

    # Celery görevi tetikle (geç import — worker hazır olmayabilir)
    try:
        from app.worker.tasks import process_tryon_task
        process_tryon_task.delay(str(tryon.id))
        logger.info(f"[TryOn {tryon.id}] Celery görevi kuyruğa alındı.")
    except Exception as exc:
        logger.warning(f"[TryOn {tryon.id}] Celery tetiklenemedi: {exc}")

    return _to_response(tryon)


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/tryon/{tryon_id}  — Durumu Sorgula
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tryon_id}",
    response_model=TryOnResponse,
    summary="Try-on işleminin durumunu getir",
)
def get_tryon(tryon_id: str, db: Session = Depends(get_db)):
    try:
        uid = uuid.UUID(tryon_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Geçersiz UUID formatı.")

    tryon = db.query(TryOn).filter(TryOn.id == uid).first()
    if not tryon:
        raise HTTPException(status_code=404, detail=f"TryOn bulunamadı: {tryon_id}")
    return _to_response(tryon)


# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────

def _to_response(tryon: TryOn) -> TryOnResponse:
    return TryOnResponse(
        id         = str(tryon.id),
        avatar_id  = str(tryon.avatar_id),
        garment_id = str(tryon.garment_id),
        status     = tryon.status,
        result_url = tryon.result_url,
        created_at = tryon.created_at,
    )
