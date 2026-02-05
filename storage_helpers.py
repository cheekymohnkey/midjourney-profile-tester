#!/usr/bin/env python3
"""
Storage helper utilities for streamlit app - provides Path-like interface with storage backend.
"""
from pathlib import Path as PathLib
from storage import get_storage
from PIL import Image
import json
from typing import Union, List


class StoragePath:
    """Path-like wrapper that uses storage backend instead of filesystem."""
    
    def __init__(self, path: Union[str, 'StoragePath']):
        if isinstance(path, StoragePath):
            self.path = path.path
        else:
            self.path = str(path).replace('\\', '/')
    
    def __truediv__(self, other):
        """Support path / filename syntax."""
        return StoragePath(f"{self.path.rstrip('/')}/{other}")
    
    def __str__(self):
        return self.path
    
    def __repr__(self):
        return f"StoragePath('{self.path}')"
    
    @property
    def name(self):
        """Get filename."""
        return self.path.split('/')[-1]
    
    @property
    def parent(self):
        """Get parent directory."""
        parts = self.path.rsplit('/', 1)
        return StoragePath(parts[0] if len(parts) > 1 else '')
    
    def exists(self):
        """Check if file exists."""
        return get_storage().exists(self.path)
    
    def mkdir(self, exist_ok=True, parents=True):
        """Create directory (no-op for S3)."""
        get_storage().ensure_directory(self.path)
    
    def unlink(self):
        """Delete file."""
        get_storage().delete(self.path)
    
    def read_text(self, encoding='utf-8'):
        """Read file as text."""
        data = get_storage().read_bytes(self.path)
        return data.decode(encoding)
    
    def write_text(self, content, encoding='utf-8'):
        """Write text to file."""
        get_storage().write_bytes(self.path, content.encode(encoding))
    
    def read_bytes(self):
        """Read file as bytes."""
        return get_storage().read_bytes(self.path)
    
    def write_bytes(self, data):
        """Write bytes to file."""
        get_storage().write_bytes(self.path, data)
    
    def glob(self, pattern):
        """List files matching pattern."""
        files = get_storage().list_files(self.path, pattern)
        return [StoragePath(f) for f in files]
    
    def with_suffix(self, suffix):
        """Change file extension."""
        base = self.path.rsplit('.', 1)[0] if '.' in self.path else self.path
        return StoragePath(f"{base}{suffix}")
    
    def open(self, mode='r', **kwargs):
        """Open file (returns file-like object)."""
        import io
        
        if 'r' in mode:
            if 'b' in mode:
                data = get_storage().read_bytes(self.path)
                return io.BytesIO(data)
            else:
                data = get_storage().read_bytes(self.path)
                return io.StringIO(data.decode('utf-8'))
        elif 'w' in mode:
            # Return a write buffer that saves on close
            return _WriteBuffer(self.path, binary='b' in mode)
        else:
            raise ValueError(f"Unsupported mode: {mode}")


class _WriteBuffer:
    """Write buffer that saves to storage on close."""
    
    def __init__(self, path: str, binary: bool = False):
        self.path = path
        self.binary = binary
        import io
        self.buffer = io.BytesIO() if binary else io.StringIO()
    
    def write(self, data):
        self.buffer.write(data)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    def close(self):
        self.buffer.seek(0)
        if self.binary:
            get_storage().write_bytes(self.path, self.buffer.read())
        else:
            content = self.buffer.read()
            get_storage().write_bytes(self.path, content.encode('utf-8'))
        self.buffer.close()


# Convenience function for backward compatibility
def Path(path: Union[str, StoragePath]) -> StoragePath:
    """Create StoragePath (replacement for pathlib.Path)."""
    return StoragePath(path)


# Image loading helper
def load_image(path: Union[str, StoragePath]) -> Image.Image:
    """Load image from storage."""
    if isinstance(path, StoragePath):
        path = path.path
    return get_storage().read_image(str(path))


# Image saving helper
def save_image(path: Union[str, StoragePath], image: Image.Image, format: str = 'JPEG', **kwargs):
    """Save image to storage."""
    if isinstance(path, StoragePath):
        path = path.path
    quality = kwargs.get('quality', 90)
    get_storage().write_image(str(path), image, format=format, quality=quality)
