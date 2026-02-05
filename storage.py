#!/usr/bin/env python3
"""
Storage abstraction layer for local and S3 storage.
Supports both local filesystem (for development) and AWS S3 (for production/Streamlit Cloud).
"""
import json
import os
from pathlib import Path
from typing import Optional, Union, BinaryIO
import io
from PIL import Image
import boto3
from botocore.exceptions import ClientError

class StorageBackend:
    """Base class for storage backends."""
    
    def read_json(self, path: str) -> dict:
        """Read and parse JSON file."""
        raise NotImplementedError
    
    def write_json(self, path: str, data: dict) -> None:
        """Write data as JSON file."""
        raise NotImplementedError
    
    def read_bytes(self, path: str) -> bytes:
        """Read file as bytes."""
        raise NotImplementedError
    
    def write_bytes(self, path: str, data: bytes) -> None:
        """Write bytes to file."""
        raise NotImplementedError
    
    def read_image(self, path: str) -> Image.Image:
        """Read and return PIL Image."""
        raise NotImplementedError
    
    def write_image(self, path: str, image: Image.Image, format: str = 'JPEG', quality: int = 90) -> None:
        """Write PIL Image to storage."""
        raise NotImplementedError
    
    def exists(self, path: str) -> bool:
        """Check if file exists."""
        raise NotImplementedError
    
    def list_files(self, directory: str, pattern: str = "*") -> list:
        """List files in directory matching pattern."""
        raise NotImplementedError
    
    def delete(self, path: str) -> None:
        """Delete a file."""
        raise NotImplementedError
    
    def ensure_directory(self, path: str) -> None:
        """Ensure directory exists (no-op for S3)."""
        pass


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_path: Path = None):
        self.base_path = base_path or Path.cwd()
    
    def _resolve_path(self, path: str) -> Path:
        """Convert path string to absolute Path object."""
        p = Path(path)
        if not p.is_absolute():
            p = self.base_path / p
        return p
    
    def read_json(self, path: str) -> dict:
        file_path = self._resolve_path(path)
        if not file_path.exists():
            return {}
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def write_json(self, path: str, data: dict) -> None:
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def read_bytes(self, path: str) -> bytes:
        file_path = self._resolve_path(path)
        with open(file_path, 'rb') as f:
            return f.read()
    
    def write_bytes(self, path: str, data: bytes) -> None:
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(data)
    
    def read_image(self, path: str) -> Image.Image:
        file_path = self._resolve_path(path)
        return Image.open(file_path)
    
    def write_image(self, path: str, image: Image.Image, format: str = 'JPEG', quality: int = 90) -> None:
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(file_path, format=format, quality=quality)
    
    def exists(self, path: str) -> bool:
        return self._resolve_path(path).exists()
    
    def list_files(self, directory: str, pattern: str = "*") -> list:
        dir_path = self._resolve_path(directory)
        if not dir_path.exists():
            return []
        return [str(p.relative_to(self.base_path)) for p in dir_path.glob(pattern)]
    
    def delete(self, path: str) -> None:
        file_path = self._resolve_path(path)
        if file_path.exists():
            file_path.unlink()
    
    def ensure_directory(self, path: str) -> None:
        dir_path = self._resolve_path(path)
        dir_path.mkdir(parents=True, exist_ok=True)


class S3Storage(StorageBackend):
    """AWS S3 storage backend."""
    
    def __init__(self, bucket_name: str, prefix: str = "", 
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 region_name: str = 'us-east-1'):
        """
        Initialize S3 storage.
        
        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix for all keys (like a root folder)
            aws_access_key_id: AWS access key (uses env vars if not provided)
            aws_secret_access_key: AWS secret key (uses env vars if not provided)
            region_name: AWS region
        """
        self.bucket_name = bucket_name
        self.prefix = prefix.rstrip('/') if prefix else ''
        
        # Initialize S3 client
        session_kwargs = {'region_name': region_name}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs['aws_access_key_id'] = aws_access_key_id
            session_kwargs['aws_secret_access_key'] = aws_secret_access_key
        
        self.s3 = boto3.client('s3', **session_kwargs)
    
    def _get_key(self, path: str) -> str:
        """Convert path to S3 key with prefix."""
        # Remove leading slash if present
        path = path.lstrip('/')
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path
    
    def read_json(self, path: str) -> dict:
        try:
            key = self._get_key(path)
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return {}
            raise
    
    def write_json(self, path: str, data: dict) -> None:
        key = self._get_key(path)
        content = json.dumps(data, indent=2)
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='application/json'
        )
    
    def read_bytes(self, path: str) -> bytes:
        key = self._get_key(path)
        response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        return response['Body'].read()
    
    def write_bytes(self, path: str, data: bytes) -> None:
        key = self._get_key(path)
        self.s3.put_object(Bucket=self.bucket_name, Key=key, Body=data)
    
    def read_image(self, path: str) -> Image.Image:
        data = self.read_bytes(path)
        return Image.open(io.BytesIO(data))
    
    def write_image(self, path: str, image: Image.Image, format: str = 'JPEG', quality: int = 90) -> None:
        key = self._get_key(path)
        buffer = io.BytesIO()
        image.save(buffer, format=format, quality=quality)
        buffer.seek(0)
        
        content_type = 'image/jpeg' if format.upper() == 'JPEG' else f'image/{format.lower()}'
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=buffer.getvalue(),
            ContentType=content_type
        )
    
    def exists(self, path: str) -> bool:
        try:
            key = self._get_key(path)
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    def list_files(self, directory: str, pattern: str = "*") -> list:
        """List files in S3 directory. Pattern matching is basic (prefix-based)."""
        prefix = self._get_key(directory).rstrip('/') + '/'
        
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            
            if 'Contents' not in response:
                return []
            
            files = []
            for obj in response['Contents']:
                key = obj['Key']
                # Remove prefix to get relative path
                if self.prefix:
                    key = key[len(self.prefix)+1:]
                files.append(key)
            
            # Basic pattern matching (only supports * as wildcard)
            if pattern != "*":
                pattern_suffix = pattern.replace("*", "")
                files = [f for f in files if f.endswith(pattern_suffix)]
            
            return files
        except ClientError:
            return []
    
    def delete(self, path: str) -> None:
        key = self._get_key(path)
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError:
            pass  # Ignore if file doesn't exist


# Global storage instance
_storage: Optional[StorageBackend] = None


def init_storage(
    use_s3: bool = None,
    bucket_name: str = None,
    s3_prefix: str = "",
    aws_access_key_id: str = None,
    aws_secret_access_key: str = None,
    region_name: str = 'us-east-1',
    local_base_path: Path = None
) -> StorageBackend:
    """
    Initialize storage backend based on configuration.
    
    Args:
        use_s3: If True, use S3. If False, use local. If None, auto-detect from env vars.
        bucket_name: S3 bucket name (required if use_s3=True)
        s3_prefix: Optional prefix for S3 keys
        aws_access_key_id: AWS access key
        aws_secret_access_key: AWS secret key
        region_name: AWS region
        local_base_path: Base path for local storage
    
    Returns:
        StorageBackend instance
    """
    global _storage
    
    # Auto-detect if not specified
    if use_s3 is None:
        use_s3 = bool(os.getenv('USE_S3', 'false').lower() in ('true', '1', 'yes'))
    
    if use_s3:
        # Get S3 config from env vars if not provided
        bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME')
        if not bucket_name:
            raise ValueError("S3_BUCKET_NAME must be provided or set in environment")
        
        s3_prefix = s3_prefix or os.getenv('S3_PREFIX', '')
        aws_access_key_id = aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY')
        region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
        
        _storage = S3Storage(
            bucket_name=bucket_name,
            prefix=s3_prefix,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        print(f"✓ Using S3 storage: s3://{bucket_name}/{s3_prefix}")
    else:
        local_base_path = local_base_path or Path.cwd()
        _storage = LocalStorage(base_path=local_base_path)
        print(f"✓ Using local storage: {local_base_path}")
    
    return _storage


def get_storage() -> StorageBackend:
    """Get the initialized storage backend."""
    global _storage
    if _storage is None:
        # Auto-initialize with defaults
        _storage = init_storage()
    return _storage
