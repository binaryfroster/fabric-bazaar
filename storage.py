"""Persistent media storage for uploads.

Bundled catalogue assets remain in ``static/images``. New seller and admin
uploads are validated with Pillow and, when object storage is configured
(S3 / Cloudflare R2 / Supabase Storage), written to that bucket with their
public URL stored in the database. When object storage is not configured
(e.g. local development) uploads fall back to the local ``static`` folder.

On a read-only serverless filesystem (Vercel) with no object storage
configured, uploads are rejected gracefully (returns ``None``) rather than
crashing the request.
"""
from __future__ import annotations

import io
import os
import uuid

from flask import current_app, url_for
from PIL import Image, UnidentifiedImageError


_FORMATS = {
    'JPEG': ('jpg', 'image/jpeg'),
    'PNG': ('png', 'image/png'),
    'WEBP': ('webp', 'image/webp'),
}


def object_storage_configured() -> bool:
    """True only when every setting needed to upload AND serve media is present."""
    c = current_app.config
    return all([
        c.get('OBJECT_STORAGE_BUCKET'),
        c.get('OBJECT_STORAGE_ACCESS_KEY_ID'),
        c.get('OBJECT_STORAGE_SECRET_ACCESS_KEY'),
        c.get('MEDIA_PUBLIC_BASE_URL'),
    ])


def media_url(value: str | None, folder: str) -> str:
    """Return the stored remote URL or the URL of a bundled static image."""
    if not value:
        value = 'placeholder.jpg'
    if value.startswith(('https://', 'http://')):
        return value
    return url_for('static', filename=f'images/{folder}/{value}')


def save_upload(file_storage, folder: str) -> str | None:
    """Validate and persist an image.

    Returns a public URL (object storage) or a bare filename (local static),
    or ``None`` when the file is missing/invalid or cannot be persisted.
    """
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return None

    data = file_storage.read()
    if not data:
        return None

    # Enforce the configured upload ceiling defensively.
    max_bytes = current_app.config.get('MAX_CONTENT_LENGTH') or 0
    if max_bytes and len(data) > max_bytes:
        current_app.logger.warning('Rejected oversized image upload (%d bytes)', len(data))
        return None

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        current_app.logger.warning('Rejected invalid image upload: %s', file_storage.filename)
        return None

    if image.format not in _FORMATS:
        current_app.logger.warning('Rejected unsupported image format: %s', image.format)
        return None

    extension, content_type = _FORMATS[image.format]
    filename = f'{uuid.uuid4().hex}.{extension}'

    if object_storage_configured():
        try:
            return _upload_to_object_storage(data, folder, filename, content_type)
        except Exception:  # pragma: no cover - network/credentials failures
            current_app.logger.exception('Object storage upload failed')
            return None

    # Local-development / self-hosted fallback. Never used when object storage
    # is configured; on a read-only serverless FS this fails cleanly.
    try:
        directory = os.path.join(current_app.root_path, 'static', 'images', folder)
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, filename), 'wb') as output:
            output.write(data)
        return filename
    except OSError:
        current_app.logger.error(
            'Cannot write upload to local disk (read-only filesystem?). '
            'Configure OBJECT_STORAGE_* to enable uploads in this environment.'
        )
        return None


def _upload_to_object_storage(data: bytes, folder: str, filename: str, content_type: str) -> str:
    import boto3

    settings = current_app.config
    prefix = settings['OBJECT_STORAGE_PREFIX'].strip('/')
    key = '/'.join(part for part in (prefix, folder, filename) if part)
    client = boto3.client(
        's3',
        region_name=settings['OBJECT_STORAGE_REGION'] or None,
        endpoint_url=settings['OBJECT_STORAGE_ENDPOINT_URL'] or None,
        aws_access_key_id=settings['OBJECT_STORAGE_ACCESS_KEY_ID'],
        aws_secret_access_key=settings['OBJECT_STORAGE_SECRET_ACCESS_KEY'],
    )
    client.put_object(
        Bucket=settings['OBJECT_STORAGE_BUCKET'],
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl='public, max-age=31536000, immutable',
    )
    return f"{settings['MEDIA_PUBLIC_BASE_URL'].rstrip('/')}/{key}"
