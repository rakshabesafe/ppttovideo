from minio import Minio
from app.core.config import settings
import io

class MinioService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_URL,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False  # Set to True if using HTTPS
        )

    def upload_file(self, bucket_name: str, object_name: str, data: io.BytesIO, length: int):
        self.client.put_object(
            bucket_name,
            object_name,
            data,
            length=length
        )
        return f"/{bucket_name}/{object_name}"

minio_service = MinioService()
