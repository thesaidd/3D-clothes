"""
app/services/storage.py
-----------------------
AWS S3 ile dosya yukleme ve URL uretme servisi.

Fonksiyonlar:
  upload_bytes_to_s3(data, s3_key, content_type) -> str  (public/presigned URL)
  upload_file_to_s3(local_path, s3_key, content_type)    -> str
  build_s3_url(s3_key)                                   -> str

Konfigurasyon icin asagidaki .env degiskenlerini tanimlayın:
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_REGION
  S3_BUCKET_NAME
  S3_PRESIGNED_EXPIRY   (opsiyonel, saniye, default 3600)
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Presigned URL gecerlilik suresi (saniye). .env ile ezilir.
_DEFAULT_EXPIRY = 3600


def _get_client():
    """Lazy boto3 S3 client olustur. Her cagri icin yeni client."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        aws_access_key_id     = os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name           = os.getenv("AWS_REGION", "eu-central-1"),
        config                = Config(retries={"max_attempts": 3, "mode": "adaptive"}),
    )


def _bucket() -> str:
    bucket = os.getenv("S3_BUCKET_NAME", "")
    if not bucket:
        raise EnvironmentError(
            "S3_BUCKET_NAME ortam degiskeni tanimlanmamis. "
            ".env dosyasina S3_BUCKET_NAME=<bucket-adiniz> satirini ekleyin."
        )
    return bucket


def build_s3_url(s3_key: str) -> str:
    """
    Dogrudan public URL olusturur.
    Bucket'in 'Block all public access' kapali olmasi gerekir.
    Gizli bucket icin upload_bytes_to_s3 / upload_file_to_s3 presigned URL doner.
    """
    region = os.getenv("AWS_REGION", "eu-central-1")
    bucket = _bucket()
    return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"


def upload_bytes_to_s3(
    data: bytes,
    s3_key: str,
    content_type: str = "application/octet-stream",
    presigned: bool = True,
    expiry: int = _DEFAULT_EXPIRY,
) -> str:
    """
    Ham bytes verisini S3'e yukler.

    Args:
        data:         Yuklenecek bytes.
        s3_key:       S3 icindeki tam obje yolu (ornegin 'uploads/cleaned/abc.png').
        content_type: MIME tipi.
        presigned:    True -> gecici imzali URL doner. False -> public URL doner.
        expiry:       Presigned URL gecerlilik suresi (saniye).

    Returns:
        Dosyaya erisim URL'si (presigned veya public).
    """
    client = _get_client()
    bucket = _bucket()

    client.put_object(
        Bucket      = bucket,
        Key         = s3_key,
        Body        = data,
        ContentType = content_type,
    )
    logger.info(f"[S3] Yuklendi: s3://{bucket}/{s3_key} ({len(data)/1024:.1f} KB)")

    if presigned:
        url = client.generate_presigned_url(
            "get_object",
            Params     = {"Bucket": bucket, "Key": s3_key},
            ExpiresIn  = expiry,
        )
        logger.debug(f"[S3] Presigned URL uretildi ({expiry}s): {url[:60]}...")
        return url

    return build_s3_url(s3_key)


def upload_file_to_s3(
    local_path: Path,
    s3_key: str,
    content_type: str = "application/octet-stream",
    presigned: bool = True,
    expiry: int = _DEFAULT_EXPIRY,
) -> str:
    """
    Disk uzerindeki bir dosyayi S3'e yukler.
    upload_bytes_to_s3 ile ayni sekilde URL doner.
    """
    data = Path(local_path).read_bytes()
    return upload_bytes_to_s3(data, s3_key, content_type, presigned, expiry)
