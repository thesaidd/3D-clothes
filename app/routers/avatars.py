"""
Avatar Router — Kullanicinin vücut ölçülerini yönetir.

Endpoints:
    POST   /api/v1/avatars/      → Yeni avatar olustur (ölçüleri kaydet)
    GET    /api/v1/avatars/      → Tüm avatarlari listele
    GET    /api/v1/avatars/{id}  → Tek avatar detayi
    PATCH  /api/v1/avatars/{id}  → Avatar bilgilerini guncelle
    DELETE /api/v1/avatars/{id}  → Avatar sil
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.avatar import Avatar
from app.models.schemas import (
    AvatarCreate,
    AvatarListResponse,
    AvatarResponse,
    AvatarUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/avatars", tags=["avatars"])

# ─────────────────────────────────────────────────────────────────
# POST /api/v1/avatars/  — Yeni Avatar Oluştur
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=AvatarResponse,
    status_code=201,
    summary="Yeni avatar profili olustur (vücut ölçüleri kaydet)",
)
def create_avatar(
    body: AvatarCreate,
    db: Session = Depends(get_db),
):
    """
    Kullanicinin cinsiyet, boy, kilo ve vücut tipi bilgilerini veritabanina kaydeder.
    3D model üretimi henüz aktif degildir (model_url = null).
    """
    avatar = Avatar(
        name       = body.name,
        gender     = body.gender,
        height_cm  = body.height_cm,
        weight_kg  = body.weight_kg,
        body_shape = body.body_shape,
        model_url  = None,  # V2'de Tripo3D / ReadyPlayerMe ile üretilecek
    )
    db.add(avatar)
    db.commit()
    db.refresh(avatar)
    logger.info(
        f"[Avatar {avatar.id}] Olusturuldu: {avatar.name!r}, "
        f"{avatar.gender}, {avatar.height_cm}cm/{avatar.weight_kg}kg, {avatar.body_shape}"
    )
    return _to_response(avatar)


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/avatars/  — Avatar Listesi
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=AvatarListResponse,
    summary="Tüm avatar profillerini listele",
)
def list_avatars(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Veritabanindaki tüm avatar kayitlarini döner (en yeni önce)."""
    items = (
        db.query(Avatar)
        .order_by(Avatar.created_at.desc())
        .limit(limit)
        .all()
    )
    return AvatarListResponse(
        total=len(items),
        items=[_to_response(a) for a in items],
    )


# ─────────────────────────────────────────────────────────────────
# GET /api/v1/avatars/{avatar_id}  — Tek Avatar
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{avatar_id}",
    response_model=AvatarResponse,
    summary="Tek bir avatar profilini getir",
)
def get_avatar(
    avatar_id: str,
    db: Session = Depends(get_db),
):
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail=f"Avatar bulunamadi: {avatar_id}")
    return _to_response(avatar)


# ─────────────────────────────────────────────────────────────────
# PATCH /api/v1/avatars/{avatar_id}  — Avatar Güncelle
# ─────────────────────────────────────────────────────────────────

@router.patch(
    "/{avatar_id}",
    response_model=AvatarResponse,
    summary="Avatar bilgilerini guncelle",
)
def update_avatar(
    avatar_id: str,
    body: AvatarUpdate,
    db: Session = Depends(get_db),
):
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail=f"Avatar bulunamadi: {avatar_id}")

    # Sadece gonderilen alanlari guncelle (exclude_unset=True ile sessiz null yazmayiz)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(avatar, field, value)

    db.commit()
    db.refresh(avatar)
    logger.info(f"[Avatar {avatar_id}] Guncellendi: {list(updates.keys())}")
    return _to_response(avatar)


# ─────────────────────────────────────────────────────────────────
# DELETE /api/v1/avatars/{avatar_id}  — Avatar Sil
# ─────────────────────────────────────────────────────────────────

@router.delete(
    "/{avatar_id}",
    status_code=204,
    summary="Avatar profilini sil",
)
def delete_avatar(
    avatar_id: str,
    db: Session = Depends(get_db),
):
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail=f"Avatar bulunamadi: {avatar_id}")
    db.delete(avatar)
    db.commit()
    logger.info(f"[Avatar {avatar_id}] Silindi.")
    # 204 No Content


# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────

def _to_response(avatar: Avatar) -> AvatarResponse:
    return AvatarResponse(
        id         = str(avatar.id),
        name       = avatar.name,
        gender     = avatar.gender,
        height_cm  = avatar.height_cm,
        weight_kg  = avatar.weight_kg,
        body_shape = avatar.body_shape,
        model_url  = avatar.model_url,
        created_at = avatar.created_at,
    )
