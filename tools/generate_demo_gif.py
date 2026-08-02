"""Gerador do GIF de demonstração do EDY Shield (Sprint 5, v2.0).

Gera ``assets/demo.gif`` a partir das screenshots oficiais reais da UI
(``assets/screenshots/*.png``) usando **apenas a stdlib** (zlib + struct).

Implementa:
- Decodificador mínimo de PNG (RGB 8-bit, color_type 2, filtros 0-4).
- Redução de resolução por amostragem (nearest neighbor).
- Encoder GIF89a com LZW (paleta 256 cores 3-3-2).

Uso:
    python tools/generate_demo_gif.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

#: Frames do demo: (arquivo da screenshot, duração em centésimos de segundo).
FRAMES: list[tuple[str, int]] = [
    ("dashboard.png", 160),
    ("hash-checker.png", 120),
    ("log-analyzer.png", 120),
    ("file-integrity-monitor.png", 180),
    ("plugins.png", 120),
    ("dashboard.png", 160),
]

OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "demo.gif"
SCREENSHOTS = Path(__file__).resolve().parents[1] / "assets" / "screenshots"

#: Tamanho de saída do GIF (reduzido p/ demo leve).
WIDTH, HEIGHT = 1280, 720


# ---------------------------------------------------------------------------
# PNG decode (RGB 8-bit)
# ---------------------------------------------------------------------------


def _read_png_rgb(path: Path) -> tuple[int, int, list[bytes]]:
    """Decodificar um PNG RGB 8-bit (color_type 2).

    Returns:
        ``(width, height, scanlines)`` — cada scanline é ``width * 3`` bytes.
    """
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"não é PNG: {path.name}")

    pos = 8
    width = height = 0
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
            if bit_depth != 8 or color_type != 2:
                raise ValueError(f"PNG não suportado: depth={bit_depth}, color={color_type}")
        elif ctype == b"IDAT":
            idat += chunk
        pos += 12 + length

    raw = zlib.decompress(idat)
    stride = width * 3
    scanlines: list[bytes] = []
    prev = bytearray(stride)
    offset = 0
    for _ in range(height):
        filt = raw[offset]
        offset += 1
        line = bytearray(raw[offset : offset + stride])
        offset += stride

        if filt == 0:
            pass
        elif filt == 1:  # Sub
            for i in range(3, stride):
                line[i] = (line[i] + line[i - 3]) & 0xFF
        elif filt == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:  # Average
            for i in range(stride):
                left = line[i - 3] if i >= 3 else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:  # Paeth
            for i in range(stride):
                a = line[i - 3] if i >= 3 else 0
                b = prev[i]
                c = prev[i - 3] if i >= 3 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        else:
            raise ValueError(f"filtro PNG inválido: {filt}")

        scanlines.append(bytes(line))
        prev = line

    return width, height, scanlines


def _resize_nearest(
    scanlines: list[bytes],
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
) -> list[bytes]:
    """Reduzir scanlines RGB para dst_w x dst_h (nearest neighbor)."""
    out: list[bytes] = []
    for y in range(dst_h):
        sy = min(int(y * src_h / dst_h), src_h - 1)
        line = bytearray(dst_w * 3)
        src_line = scanlines[sy]
        for x in range(dst_w):
            sx = min(int(x * src_w / dst_w), src_w - 1)
            base = sx * 3
            line[x * 3] = src_line[base]
            line[x * 3 + 1] = src_line[base + 1]
            line[x * 3 + 2] = src_line[base + 2]
        out.append(bytes(line))
    return out


# ---------------------------------------------------------------------------
# GIF89a encode (paleta 256 cores, LZW)
# ---------------------------------------------------------------------------


def _truncate_index(r: int, g: int, b: int) -> int:
    """Mapear RGB para índice da paleta 3-3-2 (256 cores)."""
    return ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6)


def _build_gct() -> bytes:
    """Global Color Table: 256 entradas (cores 3-3-2)."""
    entries = bytearray()
    for idx in range(256):
        r = ((idx >> 5) & 0x7) * 255 // 7
        g = ((idx >> 2) & 0x7) * 255 // 7
        b = (idx & 0x3) * 255 // 3
        entries.extend((r, g, b))
    return bytes(entries)


def _lzw_compress(pixels: bytes, min_code_size: int = 8) -> bytes:
    """Comprimir dados de imagem no formato LZW do GIF (sub-blocks)."""
    clear = 1 << min_code_size
    end = clear + 1
    code_size = min_code_size + 1
    next_code = end + 1

    table: dict[bytes, int] = {bytes([i]): i for i in range(clear)}
    bit_buffer = 0
    bit_count = 0
    out: list[int] = []

    def emit(code: int, size: int) -> None:
        nonlocal bit_buffer, bit_count
        bit_buffer |= code << bit_count
        bit_count += size
        while bit_count >= 8:
            out.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8

    emit(clear, code_size)
    w = b""
    for byte in pixels:
        wc = w + bytes([byte])
        if wc in table:
            w = wc
        else:
            emit(table[w], code_size)
            table[wc] = next_code
            next_code += 1
            if code_size < 12 and next_code == (1 << code_size):
                code_size += 1
            w = bytes([byte])
    if w:
        emit(table[w], code_size)
    emit(end, code_size)
    if bit_count > 0:
        out.append(bit_buffer & 0xFF)

    blocks = bytearray()
    for i in range(0, len(out), 255):
        chunk = bytes(out[i : i + 255])
        blocks.append(len(chunk))
        blocks.extend(chunk)
    return bytes(blocks)


def _frame_to_indices(scanlines: list[bytes]) -> bytes:
    """Converter scanlines RGB em índices da paleta 3-3-2."""
    out = bytearray()
    for line in scanlines:
        for i in range(0, len(line), 3):
            out.append(_truncate_index(line[i], line[i + 1], line[i + 2]))
    return bytes(out)


def _gif_frame(pixels: bytes, delay_cs: int) -> bytes:
    """Empacotar um frame GIF (GCE + Image Descriptor + LZW)."""
    gce = b"\x21\xf9\x04\x04" + struct.pack("<H", delay_cs) + b"\x00\x00"
    descriptor = b"\x2c" + struct.pack("<HHHH", 0, 0, WIDTH, HEIGHT) + b"\x00"
    data = _lzw_compress(pixels)
    return gce + descriptor + b"\x08" + data + b"\x00"


def build_gif() -> bytes:
    """Construir o GIF de demonstração completo."""
    gct = _build_gct()
    header = b"GIF89a"
    lsd = struct.pack("<HHBB", WIDTH, HEIGHT, 0x80 | 0x07 | 0x00, 0) + b"\x00\x00"
    body = b"".join(
        _gif_frame(_frame_to_indices(_resize_nearest(*_load_for_frame(name), WIDTH, HEIGHT)), delay)
        for name, delay in FRAMES
    )
    return header + lsd + gct + body + b"\x3b"


def _load_for_frame(name: str) -> tuple[list[bytes], int, int]:
    """Carregar screenshot na ordem esperada por _resize_nearest."""
    w, h, scanlines = _read_png_rgb(SCREENSHOTS / name)
    return scanlines, w, h


def main() -> None:
    """Gerar assets/demo.gif a partir das screenshots oficiais."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    gif = build_gif()
    OUTPUT.write_bytes(gif)
    print(f"demo.gif gerado: {OUTPUT} ({len(gif):,} bytes, {len(FRAMES)} frames)")


if __name__ == "__main__":
    main()
