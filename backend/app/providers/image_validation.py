"""생성 이미지 검증: MIME(매직 바이트), 크기, 디코딩 가능 여부, 해상도."""
from __future__ import annotations

import io

from PIL import Image

from .base import ProviderError

MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
]
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def sniff_mime(data: bytes) -> str | None:
    for magic, mime in MAGIC:
        if data.startswith(magic):
            return mime
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image(data: bytes, max_bytes: int, expected_size: str | None = None) -> tuple[str, int, int]:
    if not data or len(data) < 1024:
        raise ProviderError("bad_format", f"이미지 데이터가 비었거나 너무 작습니다 ({len(data) if data else 0} bytes)")
    if len(data) > max_bytes:
        raise ProviderError("bad_format", f"이미지가 너무 큽니다 ({len(data)} bytes)")
    mime = sniff_mime(data)
    if mime is None:
        raise ProviderError("bad_format", "지원하지 않는 이미지 형식(MIME)입니다")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
    except Exception as e:  # noqa: BLE001
        raise ProviderError("bad_format", f"이미지를 디코딩할 수 없습니다: {e}") from e
    if w < 256 or h < 256:
        raise ProviderError("bad_format", f"이미지 해상도가 너무 낮습니다 ({w}x{h})")
    if expected_size and "x" in expected_size:
        ew, eh = (int(x) for x in expected_size.split("x"))
        # 비율이 크게 다르면 슬라이드 이미지 영역에 맞지 않음 → 실패로 처리
        if abs(w / h - ew / eh) > 0.08:
            raise ProviderError("bad_format", f"이미지 비율이 요청과 다릅니다 (요청 {expected_size}, 응답 {w}x{h})")
    return mime, w, h
