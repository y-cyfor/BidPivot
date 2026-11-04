import io
import uuid

from minio import Minio

from app.config import settings


def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY.get_secret_value(),
        secret_key=settings.MINIO_SECRET_KEY.get_secret_value(),
        secure=False,
    )


def ensure_bucket():
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)


def upload_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload file to MinIO, return storage path."""
    ensure_bucket()
    storage_path = f"{uuid.uuid4()}/{filename}"
    client = get_minio_client()
    client.put_object(
        settings.MINIO_BUCKET,
        storage_path,
        io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )
    return storage_path


def get_file_url(storage_path: str) -> str:
    client = get_minio_client()
    return client.presigned_get_object(settings.MINIO_BUCKET, storage_path)


def download_file(storage_path: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, storage_path)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(storage_path: str) -> None:
    """Remove an object from MinIO. Missing objects are ignored."""
    if not storage_path:
        return
    get_minio_client().remove_object(settings.MINIO_BUCKET, storage_path)
