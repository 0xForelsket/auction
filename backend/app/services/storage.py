import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings


class StorageClient:
    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )

    @property
    def bucket(self) -> str:
        return settings.S3_BUCKET

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)

    def upload_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else None
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, **(extra or {}))
        return key

    def download_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def copy_object(self, source_key: str, dest_key: str) -> str:
        self._client.copy_object(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": source_key},
            Key=dest_key,
        )
        return dest_key


storage_client = StorageClient()


def generate_key(prefix: str, filename: str | None = None) -> str:
    suffix = ""
    if filename:
        suffix = Path(filename).suffix
    return f"{prefix}/{uuid.uuid4()}{suffix}"
