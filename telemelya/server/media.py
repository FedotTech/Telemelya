"""MinIO media layer: upload, download, cleanup."""

from __future__ import annotations

import io
from typing import Optional

from aiobotocore.session import get_session

from telemelya.server.config import settings


class MediaManager:
    """Async MinIO (S3-compatible) media manager."""

    def __init__(self) -> None:
        self._session = get_session()
        self._client = None
        self._client_ctx = None

    async def connect(self) -> None:
        protocol = "https" if settings.minio_use_ssl else "http"
        endpoint_url = f"{protocol}://{settings.minio_endpoint}"
        self._client_ctx = self._session.create_client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="us-east-1",
        )
        self._client = await self._client_ctx.__aenter__()
        await self._ensure_bucket()

    async def close(self) -> None:
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
            self._client = None

    async def _ensure_bucket(self) -> None:
        try:
            await self._client.head_bucket(Bucket=settings.minio_bucket)
        except Exception:
            await self._client.create_bucket(Bucket=settings.minio_bucket)

    def _object_key(
        self, session_id: str, file_id: str, filename: str
    ) -> str:
        return f"{session_id}/{file_id}/{filename}"

    async def upload(
        self,
        session_id: str,
        file_id: str,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        key = self._object_key(session_id, file_id, filename)
        await self._client.put_object(
            Bucket=settings.minio_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    async def download(
        self, session_id: str, file_id: str, filename: str
    ) -> Optional[bytes]:
        key = self._object_key(session_id, file_id, filename)
        try:
            response = await self._client.get_object(
                Bucket=settings.minio_bucket, Key=key
            )
            async with response["Body"] as stream:
                return await stream.read()
        except Exception:
            return None

    async def download_by_key(self, key: str) -> Optional[bytes]:
        try:
            response = await self._client.get_object(
                Bucket=settings.minio_bucket, Key=key
            )
            async with response["Body"] as stream:
                return await stream.read()
        except Exception:
            return None

    async def cleanup_session(self, session_id: str) -> None:
        prefix = f"{session_id}/"
        paginator = self._client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(
            Bucket=settings.minio_bucket, Prefix=prefix
        ):
            objects = page.get("Contents", [])
            if objects:
                delete_spec = {
                    "Objects": [{"Key": obj["Key"]} for obj in objects]
                }
                await self._client.delete_objects(
                    Bucket=settings.minio_bucket, Delete=delete_spec
                )

    async def ping(self) -> bool:
        try:
            await self._client.head_bucket(Bucket=settings.minio_bucket)
            return True
        except Exception:
            return False


media_manager = MediaManager()
