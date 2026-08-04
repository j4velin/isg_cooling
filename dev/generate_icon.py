#!/usr/bin/env python3
"""Generate the snowflake brand icon for the isg_cooling integration.

Stdlib only - no Pillow / cairo required. The same geometry drives both a
vector source (dev/icon.svg) and the raster files bundled with the
integration.

Since Home Assistant 2026.3 an integration can ship its own brand images in
``custom_components/<domain>/brand/``; these take priority over the
home-assistant/brands CDN and are served through ``/api/brands/...``. No
manifest change is required.

Outputs:
    custom_components/isg_cooling/brand/icon.png       256x256
    custom_components/isg_cooling/brand/icon@2x.png    512x512
    dev/icon.svg                                       vector source

Run:  python3 dev/generate_icon.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

# --- design parameters (fractions of the image size) -----------------------
COLOR = (41, 171, 226)      # #29ABE2 - icy blue
R_FRAC = 0.46               # arm length
W_FRAC = 0.032              # stroke half-width
BRANCHES = (0.46, 0.70)     # positions of side branches along each arm
BRANCH_LEN_FRAC = 0.26      # branch length (fraction of R)
BRANCH_ANGLE = 60           # degrees off the arm

_REPO = Path(__file__).resolve().parent.parent
BRAND_DIR = _REPO / "custom_components" / "isg_cooling" / "brand"
SVG_PATH = _REPO / "dev" / "icon.svg"


def _point(cx: float, cy: float, angle_deg: float, r: float) -> tuple[float, float]:
    """Point at distance r and angle (0=+x, CCW) in image coords (y down)."""
    rad = math.radians(angle_deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def segments(n: int) -> list[tuple[float, float, float, float]]:
    """Return the snowflake as a list of (x0, y0, x1, y1) segments."""
    c = (n - 1) / 2.0
    R = R_FRAC * n
    L = BRANCH_LEN_FRAC * R
    segs: list[tuple[float, float, float, float]] = []
    for k in range(6):
        arm = 90 + 60 * k  # one point straight up
        tip = _point(c, c, arm, R)
        segs.append((c, c, tip[0], tip[1]))
        for frac in BRANCHES:
            base = _point(c, c, arm, frac * R)
            for side in (+1, -1):
                end = _point(base[0], base[1], arm + side * BRANCH_ANGLE, L)
                segs.append((base[0], base[1], end[0], end[1]))
    return segs


def _dist2_to_seg(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        ddx, ddy = px - ax, py - ay
        return ddx * ddx + ddy * ddy
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    ddx = px - (ax + t * dx)
    ddy = py - (ay + t * dy)
    return ddx * ddx + ddy * ddy


def _png_bytes(n: int) -> bytes:
    segs = segments(n)
    w = W_FRAC * n
    r, g, b = COLOR
    raw = bytearray()
    for y in range(n):
        raw.append(0)  # filter type 0 for this scanline
        py = y + 0.5
        for x in range(n):
            px = x + 0.5
            best = 1e18
            for (ax, ay, bx, by) in segs:
                d2 = _dist2_to_seg(px, py, ax, ay, bx, by)
                if d2 < best:
                    best = d2
            d = math.sqrt(best)
            cov = w - d + 0.5  # analytic 1px anti-aliasing
            if cov <= 0.0:
                raw.extend((0, 0, 0, 0))
            else:
                a = 255 if cov >= 1.0 else int(cov * 255 + 0.5)
                raw.extend((r, g, b, a))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _svg(n: int = 256) -> str:
    stroke = 2 * W_FRAC * n
    hexc = "#%02X%02X%02X" % COLOR
    lines = [
        f'  <line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}"/>'
        for (x0, y0, x1, y1) in segments(n)
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" '
        f'width="{n}" height="{n}">\n'
        f'  <g fill="none" stroke="{hexc}" stroke-width="{stroke:.2f}" '
        f'stroke-linecap="round">\n'
        + "\n".join(lines)
        + "\n  </g>\n</svg>\n"
    )


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    SVG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_PATH.write_text(_svg(256), encoding="utf-8")
    (BRAND_DIR / "icon.png").write_bytes(_png_bytes(256))
    (BRAND_DIR / "icon@2x.png").write_bytes(_png_bytes(512))
    for p in (SVG_PATH, BRAND_DIR / "icon.png", BRAND_DIR / "icon@2x.png"):
        print(f"wrote {p.relative_to(_REPO)} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
