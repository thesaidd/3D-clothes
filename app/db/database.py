"""
app/db/database.py
------------------
SQLAlchemy engine, session factory ve FastAPI dependency.

Kullanim:
    from app.db.database import get_db, engine, Base

    # Endpoint'lerde:
    def my_endpoint(db: Session = Depends(get_db)): ...

    # Tablo olusturma (main.py startup'ta):
    Base.metadata.create_all(bind=engine)
"""
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# ── Engine ────────────────────────────────────────────────────────
# pool_pre_ping: kopuk baglantilari otomatik yenile
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=settings.DEBUG,   # DEBUG=True ise SQL sorgularini logla
)

# ── Session Factory ───────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# ── Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── FastAPI Dependency ────────────────────────────────────────────
def get_db():
    """
    Her request icin yeni bir DB session olusturur, islem bitince kapatir.

    Kullanim:
        from app.db.database import get_db
        from sqlalchemy.orm import Session

        @router.get("/...")
        def my_view(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Context Manager (Celery worker icin) ─────────────────────────
@contextmanager
def get_db_context():
    """
    'with' blogu icinde kullanim icin context manager versiyonu.
    Celery task'larda Depends() kullanamayiz, bu fonksiyonu kullaniriz.

    Kullanim:
        from app.db.database import get_db_context
        with get_db_context() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
