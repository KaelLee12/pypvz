"""High-resolution rendering layer.

Game logic keeps working in the original 800x600 coordinate space, while every
image is backed by a surface that is ``SCALE`` times larger. ``HDSurface``
wraps such a backing surface and exposes the *logical* geometry, so existing
code that does ``surface.blit(image, rect)`` / ``image.get_rect()`` keeps
working unchanged. ``Display`` owns the window and presents the full-size
frame through a GPU texture, which on HiDPI screens maps 1:1 to physical
pixels.
"""

from __future__ import annotations

import logging
import os
import weakref
from typing import Iterable, Sequence

import pygame as pg
from pygame._sdl2.video import Renderer, Texture

from . import constants as c

logger = logging.getLogger('main')

SCALE: int = c.RENDER_SCALE
RENDER_SIZE: tuple[int, int] = (
    c.SCREEN_WIDTH * SCALE,
    c.SCREEN_HEIGHT * SCALE,
)

# Reference pixel formats used by convert()/convert_alpha(); no display surface
# exists because the window is driven by the SDL renderer.
_REF_RGB = pg.Surface((1, 1), 0, 32)
_REF_RGBA = pg.Surface((1, 1), pg.SRCALPHA, 32)

Color = tuple[int, int, int] | tuple[int, int, int, int] | pg.Color
RectLike = pg.Rect | Sequence[int]


def _up(v: int | float) -> int:
    return int(round(v * SCALE))


def _down(v: int | float) -> int:
    return int(v // SCALE)


def _up_rect(r: RectLike) -> pg.Rect:
    r = pg.Rect(r)
    return pg.Rect(_up(r.x), _up(r.y), _up(r.w), _up(r.h))


def _up_dest(dest: RectLike | tuple[int, int]) -> tuple[int, int]:
    if isinstance(dest, pg.Rect):
        return _up(dest.x), _up(dest.y)
    return _up(dest[0]), _up(dest[1])


class HDSurface:
    """A surface addressed in logical coordinates, stored at ``SCALE`` x."""

    __slots__ = ('hd',)

    def __init__(self, hd: pg.Surface):
        self.hd = hd

    # ---- geometry (logical units) -------------------------------------
    def get_width(self) -> int:
        return _down(self.hd.get_width())

    def get_height(self) -> int:
        return _down(self.hd.get_height())

    def get_size(self) -> tuple[int, int]:
        return self.get_width(), self.get_height()

    def get_rect(self, **kwargs: int | tuple[int, int]) -> pg.Rect:
        rect = pg.Rect(0, 0, self.get_width(), self.get_height())
        for key, value in kwargs.items():
            setattr(rect, key, value)
        return rect

    # ---- drawing --------------------------------------------------------
    def blit(
        self,
        source: HDSurface,
        dest: RectLike | tuple[int, int],
        area: RectLike | None = None,
        special_flags: int = 0,
    ) -> pg.Rect:
        hd_area = _up_rect(area) if area is not None else None
        r = self.hd.blit(source.hd, _up_dest(dest), hd_area, special_flags)
        return pg.Rect(_down(r.x), _down(r.y), _down(r.w), _down(r.h))

    def blits(
        self,
        blit_sequence: Iterable[tuple],
        doreturn: int = 1,
    ) -> list[pg.Rect] | None:
        # Each item is (source, dest[, area[, special_flags]]), as pg.Surface.blits
        rects = [self.blit(*item) for item in blit_sequence]
        return rects if doreturn else None

    def fill(self, color: Color, rect: RectLike | None = None) -> pg.Rect:
        r = self.hd.fill(color, _up_rect(rect) if rect is not None else None)
        return pg.Rect(_down(r.x), _down(r.y), _down(r.w), _down(r.h))

    # ---- pixel format / alpha ------------------------------------------
    def set_alpha(self, value: int | None) -> None:
        self.hd.set_alpha(value)

    def get_alpha(self) -> int | None:
        return self.hd.get_alpha()

    def set_colorkey(self, color: Color | None) -> None:
        self.hd.set_colorkey(color)

    def get_colorkey(self) -> Color | None:
        return self.hd.get_colorkey()

    def convert(self) -> HDSurface:
        return HDSurface(self.hd.convert(_REF_RGB))

    def convert_alpha(self) -> HDSurface:
        return HDSurface(self.hd.convert(_REF_RGBA))

    def copy(self) -> HDSurface:
        return HDSurface(self.hd.copy())

    def get_at(self, pos: tuple[int, int]) -> pg.Color:
        return self.hd.get_at((_up(pos[0]), _up(pos[1])))

    def get_bitsize(self) -> int:
        return self.hd.get_bitsize()

    def get_flags(self) -> int:
        return self.hd.get_flags()


def Surface(size: tuple[int, int], flags: int = 0) -> HDSurface:
    """Logical-size replacement for ``pg.Surface``."""
    return HDSurface(pg.Surface((_up(size[0]), _up(size[1])), flags, 32))


def load_image(path: str) -> HDSurface:
    """Load an image file from the HD resource tree (already ``SCALE`` x)."""
    return HDSurface(pg.image.load(path))


def scale(surface: HDSurface, size: tuple[int, int]) -> HDSurface:
    """Replacement for ``pg.transform.scale`` (uses smooth scaling)."""
    hd_size = (max(1, _up(size[0])), max(1, _up(size[1])))
    if surface.hd.get_bitsize() < 24:
        return HDSurface(pg.transform.scale(surface.hd, hd_size))
    return HDSurface(pg.transform.smoothscale(surface.hd, hd_size))


# Animation frames are immutable once loaded, so per-frame derived data
# (collision masks, mirrored frames) is cached per source surface instead of
# being recomputed for every sprite on every tick.
_flip_cache: weakref.WeakKeyDictionary[
    pg.Surface, dict[tuple[bool, bool], HDSurface]
] = weakref.WeakKeyDictionary()
_mask_cache: weakref.WeakKeyDictionary[
    pg.Surface, dict[int, pg.Mask]
] = weakref.WeakKeyDictionary()


def flip(surface: HDSurface, flip_x: bool, flip_y: bool) -> HDSurface:
    variants = _flip_cache.setdefault(surface.hd, {})
    key = (bool(flip_x), bool(flip_y))
    flipped = variants.get(key)
    if flipped is None:
        flipped = HDSurface(pg.transform.flip(surface.hd, flip_x, flip_y))
        variants[key] = flipped
    return flipped


def rotate(surface: HDSurface, angle: float) -> HDSurface:
    return HDSurface(pg.transform.rotate(surface.hd, angle))


# Fading variants keyed by base surface, and each variant's base, so that
# re-fading an already faded image never compounds the alpha.
_alpha_cache: weakref.WeakKeyDictionary[
    pg.Surface, dict[int, HDSurface]
] = weakref.WeakKeyDictionary()
_alpha_base: weakref.WeakKeyDictionary[
    pg.Surface, weakref.ref[pg.Surface]
] = weakref.WeakKeyDictionary()


def with_alpha(surface: HDSurface, alpha: int) -> HDSurface:
    """Return a translucent variant of ``surface`` without mutating it.

    ``Surface.set_alpha`` on a per-pixel-alpha image forces SDL's slow
    modulated blit (~5x slower), and mutates frames shared by every sprite.
    Instead the alpha is baked into a cached copy, which blits on the fast
    path.
    """
    base_ref = _alpha_base.get(surface.hd)
    base_hd = base_ref() if base_ref is not None else None
    if base_hd is None:
        base_hd = surface.hd
    if alpha >= 255:
        return surface if base_hd is surface.hd else HDSurface(base_hd)

    variants = _alpha_cache.setdefault(base_hd, {})
    faded = variants.get(alpha)
    if faded is None:
        hd_copy = base_hd.copy()
        if hd_copy.get_flags() & pg.SRCALPHA:
            hd_copy.fill(
                (255, 255, 255, alpha), special_flags=pg.BLEND_RGBA_MULT
            )
        else:   # colorkey / opaque image: plain surface alpha is cheap here
            hd_copy.set_alpha(alpha)
        faded = HDSurface(hd_copy)
        variants[alpha] = faded
        _alpha_base[hd_copy] = weakref.ref(base_hd)
    return faded


def mask_from_surface(surface: HDSurface, threshold: int = 127) -> pg.Mask:
    """Collision mask in logical resolution (cached per source surface)."""
    masks = _mask_cache.setdefault(surface.hd, {})
    mask = masks.get(threshold)
    if mask is None:
        w, h = surface.get_size()
        logical = pg.transform.scale(surface.hd, (max(1, w), max(1, h)))
        mask = pg.mask.from_surface(logical, threshold)
        masks[threshold] = mask
    return mask


def draw_rect(
    surface: HDSurface, color: Color, rect: RectLike, width: int = 0
) -> pg.Rect:
    r = pg.draw.rect(surface.hd, color, _up_rect(rect), _up(width))
    return pg.Rect(_down(r.x), _down(r.y), _down(r.w), _down(r.h))


class Font:
    """Replacement for ``pg.font.Font`` rendering at ``SCALE`` x."""

    def __init__(self, path: str | None, size: int):
        self._font = pg.font.Font(path, _up(size))

    @property
    def bold(self) -> bool:
        return self._font.bold

    @bold.setter
    def bold(self, value: bool) -> None:
        self._font.bold = value

    @property
    def italic(self) -> bool:
        return self._font.italic

    @italic.setter
    def italic(self, value: bool) -> None:
        self._font.italic = value

    def render(
        self,
        text: str,
        antialias: bool,
        color: Color,
        background: Color | None = None,
    ) -> HDSurface:
        return HDSurface(self._font.render(text, antialias, color, background))

    def size(self, text: str) -> tuple[int, int]:
        w, h = self._font.size(text)
        return _down(w), _down(h)


class Display:
    """Window + GPU presenter for the full-resolution frame."""

    def __init__(self, title: str, logical_size: tuple[int, int]):
        self.logical_size = logical_size
        self.window = pg.Window(title, size=logical_size, allow_high_dpi=True)
        self.renderer = Renderer(self.window, accelerated=-1, vsync=True)
        self.renderer.draw_color = (0, 0, 0, 255)
        self.texture = Texture(self.renderer, RENDER_SIZE, streaming=True)
        self.texture.blend_mode = pg.BLENDMODE_NONE
        # Frame surface in the exact pixel layout the texture expects.
        self.screen = HDSurface(pg.Surface(RENDER_SIZE, 0, 32))
        self.fullscreen = False

    # ---- window ---------------------------------------------------------
    def set_caption(self, title: str) -> None:
        self.window.title = title

    def set_icon(self, path: str) -> None:
        try:
            self.window.set_icon(pg.image.load(path))
        except pg.error as e:   # icon is optional
            logger.warning(f'无法设置窗口图标: {e}')

    def set_fullscreen(self, enabled: bool) -> None:
        if enabled == self.fullscreen:
            return
        if enabled:
            self.window.set_fullscreen(True)
        else:
            self.window.set_windowed()
            self.window.size = self.logical_size
        self.fullscreen = enabled

    # ---- geometry -------------------------------------------------------
    def _dest_rect(self) -> pg.Rect:
        """Letterboxed destination of the frame, in output pixels."""
        out = self.renderer.get_viewport()
        ow, oh = out.w, out.h
        lw, lh = self.logical_size
        k = min(ow / lw, oh / lh)
        w, h = int(lw * k), int(lh * k)
        return pg.Rect((ow - w) // 2, (oh - h) // 2, w, h)

    def to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Map a window-space mouse position to logical 800x600 coordinates."""
        ww, wh = self.window.size
        out = self.renderer.get_viewport()
        dst = self._dest_rect()
        px = pos[0] * out.w / max(ww, 1)
        py = pos[1] * out.h / max(wh, 1)
        lx = (px - dst.x) * self.logical_size[0] / max(dst.w, 1)
        ly = (py - dst.y) * self.logical_size[1] / max(dst.h, 1)
        return int(lx), int(ly)

    def mouse_pos(self) -> tuple[int, int]:
        return self.to_logical(pg.mouse.get_pos())

    # ---- presenting -----------------------------------------------------
    def present(self) -> None:
        self.texture.update(self.screen.hd)
        self.renderer.clear()
        self.texture.draw(dstrect=self._dest_rect())
        self.renderer.present()


def hd_image_dir() -> str:
    """Resource directory matching ``SCALE``."""
    if SCALE == 1:
        return c.PATH_IMG_DIR
    hd_dir = c.PATH_IMG_HD_DIR
    if not os.path.isdir(hd_dir):
        raise FileNotFoundError(f'缺少高清图片资源目录: {hd_dir}')
    return hd_dir
