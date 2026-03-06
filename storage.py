import os
from io import BytesIO

import boto3


class R2Storage:
    def __init__(self) -> None:
        self.bucket_name = os.environ.get("R2_BUCKET_NAME", "").strip()
        self.endpoint_url = os.environ.get("R2_ENDPOINT_URL", "").strip() or None
        self.access_key_id = os.environ.get("R2_ACCESS_KEY_ID", "").strip() or None
        self.secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip() or None
        self.public_url = os.environ.get("R2_PUBLIC_URL", "").strip().rstrip("/")

        self.s3 = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name="auto",
        )

    def upload_file(self, file_data, object_name: str, content_type: str) -> None:
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

    def get_file_bytes(self, object_name: str) -> BytesIO:
        if not self.bucket_name:
            raise RuntimeError("R2_BUCKET_NAME is not configured.")

        file_buffer = BytesIO()
        self.s3.download_fileobj(self.bucket_name, object_name, file_buffer)
        file_buffer.seek(0)
        return file_buffer

    def get_url(self, object_name: str) -> str:
        clean_name = object_name.lstrip("/")
        if self.public_url:
            return f"{self.public_url}/{clean_name}"

        if not self.bucket_name:
            raise RuntimeError("R2_BUCKET_NAME is not configured.")

        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": clean_name},
            ExpiresIn=3600,
        )


storage = R2Storage()
