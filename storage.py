import logging
import os
from io import BytesIO

import boto3

LOGGER = logging.getLogger(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


class R2Storage:
    def __init__(self) -> None:
        self.bucket_name = os.environ.get("R2_BUCKET_NAME", "").strip()
        self.endpoint_url = os.environ.get("R2_ENDPOINT_URL", "").strip() or None
        self.access_key_id = os.environ.get("R2_ACCESS_KEY_ID", "").strip() or None
        self.secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip() or None
        self.public_url = os.environ.get("R2_PUBLIC_URL", "").strip().rstrip("/")
        self.s3 = None

        if self.access_key_id and self.secret_access_key and self.endpoint_url:
            self.s3 = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
            )
        else:
            LOGGER.warning(
                "R2 storage is not fully configured. Falling back to local static file operations."
            )

    def _local_path(self, object_name: str) -> str:
        clean_name = object_name.lstrip("/").replace("\\", "/")
        return os.path.join(STATIC_DIR, clean_name)

    def upload_file(self, file_data, object_name: str, content_type: str) -> None:
        if self.s3:
            if not self.bucket_name:
                raise RuntimeError("R2_BUCKET_NAME is not configured.")
            if hasattr(file_data, "seek"):
                file_data.seek(0)
            self.s3.upload_fileobj(
                file_data,
                self.bucket_name,
                object_name,
                ExtraArgs={"ContentType": content_type},
            )
            return

        local_path = self._local_path(object_name)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if hasattr(file_data, "seek"):
            file_data.seek(0)
        data = file_data.read() if hasattr(file_data, "read") else file_data
        if isinstance(data, str):
            data = data.encode("utf-8")
        with open(local_path, "wb") as output_file:
            output_file.write(data)

    def get_file_bytes(self, object_name: str) -> BytesIO:
        if self.s3:
            if not self.bucket_name:
                raise RuntimeError("R2_BUCKET_NAME is not configured.")
            file_buffer = BytesIO()
            self.s3.download_fileobj(self.bucket_name, object_name, file_buffer)
            file_buffer.seek(0)
            return file_buffer

        local_path = self._local_path(object_name)
        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Local storage file not found: {local_path}")
        with open(local_path, "rb") as input_file:
            file_buffer = BytesIO(input_file.read())
        file_buffer.seek(0)
        return file_buffer

    def get_url(self, object_name: str) -> str:
        clean_name = object_name.lstrip("/")
        if self.s3:
            if self.public_url:
                return f"{self.public_url}/{clean_name}"
            if not self.bucket_name:
                raise RuntimeError("R2_BUCKET_NAME is not configured.")
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": clean_name},
                ExpiresIn=3600,
            )

        return f"/static/{clean_name}"

    def delete_file(self, object_name: str) -> None:
        if not self.bucket_name:
            raise RuntimeError("R2_BUCKET_NAME is not configured.")
        if not self.s3:
            return
        self.s3.delete_object(Bucket=self.bucket_name, Key=object_name)


storage = R2Storage()
