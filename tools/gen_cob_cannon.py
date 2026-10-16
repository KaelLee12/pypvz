"""Generate Cob Cannon sprites procedurally.

The original game assets for the Cob Cannon are not part of this repository,
so the frames are drawn with pygame primitives at a high supersampling factor
and downscaled into both resource trees:

    resources/graphics     (1x, logical size)
    resources/graphics_hd  (2x, RENDER_SCALE)

Usage (Mac/zsh):
    uv run python tools/gen_cob_cannon.py
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame as pg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIRS: dict[int, Path] = {
    1: ROOT / 'resources' / 'graphics',
    2: ROOT / 'resources' / 'graphics_hd',
}
SS = 8  # supersampling factor relative to the logical size

# Palette; pure black is avoided because the loader keys it out
OUTLINE = (34, 52, 18)
HUSK_DARK = (58, 120, 34)
HUSK = (92, 168, 52)
HUSK_LIGHT = (150, 214, 92)
COB_DARK = (196, 132, 18)
COB = (246, 196, 40)
COB_LIGHT = (255, 236, 120)
WOOD_DARK = (92, 56, 26)
WOOD = (150, 96, 46)
WOOD_LIGHT = (196, 140, 76)
METAL = (120, 124, 132)
RED = (220, 40, 30)
RED_LIGHT = (255, 120, 90)

CANNON_SIZE = (160, 100)  # logical, spans two lawn cells
BULLET_SIZE = (64, 26)
TARGET_SIZE = (64, 64)

Painter = Callable[[pg.Surface], None]


def _s(v: float) -> int:
    return int(round(v * SS))


def _canvas(size: tuple[int, int]) -> pg.Surface:
    surface = pg.Surface((_s(size[0]), _s(size[1])), pg.SRCALPHA, 32)
    surface.fill((0, 0, 0, 0))
    return surface


def _ellipse(
    surface: pg.Surface,
    color: tuple[int, int, int],
    rect: tuple[float, float, float, float],
    outline: int = 2,
) -> None:
    r = pg.Rect(_s(rect[0]), _s(rect[1]), _s(rect[2]), _s(rect[3]))
    pg.draw.ellipse(surface, OUTLINE, r)
    pg.draw.ellipse(surface, color, r.inflate(-_s(outline), -_s(outline)))


def _poly(
    surface: pg.Surface,
    color: tuple[int, int, int],
    points: list[tuple[float, float]],
    outline: float = 1.2,
) -> None:
    pts = [(_s(x), _s(y)) for x, y in points]
    pg.draw.polygon(surface, color, pts)
    pg.draw.polygon(surface, OUTLINE, pts, _s(outline))


def _leaf(
    cx: float,
    base_y: float,
    length: float,
    width: float,
    tip_dx: float,
) -> list[tuple[float, float]]:
    """Leaf polygon growing upward from (cx, base_y), tip shifted by tip_dx."""
    pts_left: list[tuple[float, float]] = []
    pts_right: list[tuple[float, float]] = []
    steps = 12
    for i in range(steps + 1):
        t = i / steps
        y = base_y - length * t
        half = width / 2 * math.sin(math.pi * min(1.0, t * 1.15))
        x = cx + tip_dx * t * t
        pts_left.append((x - half, y))
        pts_right.append((x + half, y))
    return pts_left + pts_right[::-1]


def _draw_cob(
    surface: pg.Surface,
    rect: tuple[float, float, float, float],
    glow: float = 0.0,
) -> None:
    """Corn cob lying horizontally, tip pointing right."""
    x, y, w, h = rect
    body = pg.Rect(_s(x), _s(y), _s(w), _s(h))
    pg.draw.ellipse(surface, OUTLINE, body)
    pg.draw.ellipse(surface, COB_DARK, body.inflate(-_s(2), -_s(2)))
    light = tuple(
        min(255, int(c + (255 - c) * glow)) for c in COB
    )
    cols = max(4, int(w / 5))
    rows = max(3, int(h / 5))
    for row in range(rows):
        for col in range(cols):
            u = (col + 0.5 + 0.5 * (row % 2)) / cols
            v = (row + 0.5) / rows
            # stay inside the ellipse
            if ((u - 0.5) / 0.5) ** 2 + ((v - 0.5) / 0.5) ** 2 > 0.82:
                continue
            kx = x + u * w
            ky = y + v * h
            kr = min(w / cols, h / rows) * 0.46
            pg.draw.circle(surface, light, (_s(kx), _s(ky)), _s(kr))
            pg.draw.circle(
                surface,
                COB_LIGHT,
                (_s(kx - kr * 0.3), _s(ky - kr * 0.3)),
                _s(kr * 0.35),
            )


def _draw_barrel(ready: bool, sway: float, glow: float) -> pg.Surface:
    """Horizontal husk barrel (muzzle on the right) before rotation."""
    w, h = 132, 52
    surface = _canvas((w, h))
    # back husk shell
    _ellipse(surface, HUSK_DARK, (4, 8, w - 8, h - 14))
    if ready:
        _draw_cob(surface, (16, 12, w - 30, h - 26), glow)
    else:
        # empty chamber
        _ellipse(surface, (40, 86, 26), (18, 16, w - 34, h - 30), 1.5)
    # front leaves wrapping around the lower half, tips toward the muzzle
    for i, (x0, ln, wd) in enumerate(
        ((14, 30, 22), (40, 34, 24), (68, 34, 24), (96, 28, 20))
    ):
        color = HUSK if i % 2 == 0 else HUSK_LIGHT
        tip = ln * 0.7 + sway * (1 + i * 0.3)
        _poly(surface, color, _leaf(x0, h - 3, ln, wd, tip))
    # muzzle ring
    _ellipse(surface, HUSK_DARK, (w - 18, 10, 14, h - 18), 1.5)
    _ellipse(surface, (40, 86, 26), (w - 15, 15, 8, h - 28), 1.0)
    return surface


def _draw_wheel(surface: pg.Surface, cx: float, cy: float, r: float,
                spin: float) -> None:
    pg.draw.circle(surface, OUTLINE, (_s(cx), _s(cy)), _s(r))
    pg.draw.circle(surface, WOOD_DARK, (_s(cx), _s(cy)), _s(r - 1))
    pg.draw.circle(surface, WOOD, (_s(cx), _s(cy)), _s(r - 3.5))
    for k in range(6):
        a = spin + k * math.pi / 3
        pg.draw.line(
            surface,
            WOOD_DARK,
            (_s(cx), _s(cy)),
            (_s(cx + math.cos(a) * (r - 3)), _s(cy + math.sin(a) * (r - 3))),
            _s(1.6),
        )
    pg.draw.circle(surface, METAL, (_s(cx), _s(cy)), _s(3))
    pg.draw.circle(surface, OUTLINE, (_s(cx), _s(cy)), _s(3), _s(0.8))


def _paint_cannon(
    ready: bool,
    sway: float,
    glow: float = 0.0,
    recoil: float = 0.0,
    tilt: float = 0.0,
) -> Painter:
    def paint(surface: pg.Surface) -> None:
        # cart: two wooden planks with a leafy base
        _poly(
            surface,
            WOOD,
            [(18, 70), (142, 70), (136, 82), (24, 82)],
        )
        pg.draw.line(surface, WOOD_LIGHT, (_s(24), _s(73)), (_s(136), _s(73)),
                     _s(1.5))
        # base leaves
        for x0, tip in ((30, -10), (58, -6), (102, 6), (130, 10)):
            _poly(surface, HUSK_DARK, _leaf(x0, 74, 22, 14, tip + sway))
        # barrel, rotated so the muzzle points up and to the right
        barrel = _draw_barrel(ready, sway, glow)
        rotated = pg.transform.rotozoom(barrel, 24 + tilt, 1.0)
        rect = rotated.get_rect(
            center=(_s(80 - recoil * 0.9), _s(48 + recoil * 0.4))
        )
        surface.blit(rotated, rect)
        # front wheels drawn over the barrel's tail
        _draw_wheel(surface, 40, 84, 14, sway * 0.05)
        _draw_wheel(surface, 118, 84, 14, sway * 0.05)

    return paint


def _paint_bullet(surface: pg.Surface) -> None:
    w, h = BULLET_SIZE
    # husk tail
    _poly(surface, HUSK, [(2, h / 2), (16, 3), (20, h / 2), (16, h - 3)])
    _poly(surface, HUSK_LIGHT, [(6, h / 2 + 1), (18, 6), (22, h / 2 + 2)])
    _draw_cob(surface, (12, 2, w - 14, h - 4), 0.15)


def _paint_target(surface: pg.Surface) -> None:
    w, h = TARGET_SIZE
    cx, cy = w / 2, h / 2
    for r, color, width in ((28, RED, 4), (16, RED_LIGHT, 2.5)):
        pg.draw.circle(surface, OUTLINE, (_s(cx), _s(cy)), _s(r + 1),
                       _s(width + 2))
        pg.draw.circle(surface, color, (_s(cx), _s(cy)), _s(r), _s(width))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        start = (_s(cx + dx * 8), _s(cy + dy * 8))
        end = (_s(cx + dx * 31), _s(cy + dy * 31))
        pg.draw.line(surface, OUTLINE, start, end, _s(5))
        pg.draw.line(surface, RED, start, end, _s(3))
    pg.draw.circle(surface, RED, (_s(cx), _s(cy)), _s(3))


def _save(
    painter: Painter, size: tuple[int, int], rel: str, name: str
) -> pg.Surface:
    big = _canvas(size)
    painter(big)
    hd_surface: pg.Surface | None = None
    for scale, base in OUT_DIRS.items():
        out = pg.transform.smoothscale(big, (size[0] * scale, size[1] * scale))
        path = base / rel / f'{name}.png'
        path.parent.mkdir(parents=True, exist_ok=True)
        pg.image.save(out, str(path))
        if scale == 2:
            hd_surface = out
    assert hd_surface is not None
    return hd_surface


def _save_frames(
    painters: list[Painter], size: tuple[int, int], rel: str, name: str
) -> pg.Surface:
    first: pg.Surface | None = None
    for i, painter in enumerate(painters):
        surface = _save(painter, size, f'{rel}/{name}', f'{name}_{i}')
        first = first or surface
    assert first is not None
    return first


def _make_card(thumbnail: pg.Surface) -> None:
    """Reuse an existing seed packet and repaint its plant window."""
    template = pg.image.load(str(OUT_DIRS[2] / 'Cards' / 'card_cherrybomb.png'))
    card = template.copy()
    window = pg.Rect(14, 36, 172, 172)
    top, mid, ground = (188, 245, 243), (222, 252, 228), (193, 228, 160)
    for y in range(window.top, window.bottom):
        t = (y - window.top) / max(1, window.h - 1)
        k = min(1.0, t / 0.55)
        color = tuple(int(a + (b - a) * k) for a, b in zip(top, mid))
        pg.draw.line(card, color, (window.left, y), (window.right - 1, y))
    for x in range(window.left, window.right):
        hill = window.bottom - 30 + int(6 * math.sin(x / 18))
        pg.draw.line(card, ground, (x, hill), (x, window.bottom - 1))
    # restore the window frame where the template's plant overlapped it,
    # using a clean row of the frame as reference
    for x in (*range(11, 16), *range(184, 191)):
        frame_color = template.get_at((x, 60))
        pg.draw.line(card, frame_color, (x, window.top), (x, window.bottom - 1))
    thumb_w = window.w - 6
    thumb_h = int(thumbnail.get_height() * thumb_w / thumbnail.get_width())
    thumb = pg.transform.smoothscale(thumbnail, (thumb_w, thumb_h))
    card.blit(
        thumb,
        thumb.get_rect(midbottom=(window.centerx, window.bottom - 6)),
    )
    for scale, base in OUT_DIRS.items():
        out = card if scale == 2 else pg.transform.smoothscale(
            card, (card.get_width() // 2, card.get_height() // 2)
        )
        pg.image.save(out, str(base / 'Cards' / 'card_cobcannon.png'))


def main() -> None:
    pg.init()
    n = 8
    sways = [math.sin(2 * math.pi * i / n) * 2 for i in range(n)]
    idle = _save_frames(
        [_paint_cannon(False, s) for s in sways],
        CANNON_SIZE, 'Plants/CobCannon', 'CobCannon',
    )
    del idle
    ready = _save_frames(
        [
            _paint_cannon(True, s, glow=0.25 + 0.25 * math.sin(
                2 * math.pi * i / n))
            for i, s in enumerate(sways)
        ],
        CANNON_SIZE, 'Plants/CobCannon', 'CobCannonReady',
    )
    recoils = (8, 6, 4, 2, 1, 0)
    _save_frames(
        [_paint_cannon(False, 0, recoil=r, tilt=r * 0.6) for r in recoils],
        CANNON_SIZE, 'Plants/CobCannon', 'CobCannonFire',
    )
    _save_frames([_paint_bullet], BULLET_SIZE, 'Bullets', 'CobBullet')
    _save_frames([_paint_target], TARGET_SIZE, 'Plants/CobCannon',
                 'CobCannonTarget')
    _make_card(ready)
    pg.quit()


if __name__ == '__main__':
    main()
