"""主菜单和关卡菜单里的阳光相关选项。"""

from __future__ import annotations

from collections.abc import Sequence

import pygame as pg

from .. import constants as c
from .. import hd

# 菜单每次加减的阳光。0 起按该步长增加，顶到上限时收在 SUN_VALUE_CAP。
SUN_ADJUST_STEP = 50

LABEL_X = 275
# 石碑上半部印着全屏说明，大约到 y=200；音量从 y=282 起。新选项放在两者之间。
AUTO_COLLECT_TEXT_POS = (LABEL_X, 208)
INIT_SUN_TEXT_POS = (LABEL_X, 246)
AUTO_COLLECT_RECT = pg.Rect(270, 206, 170, 30)
INIT_SUN_MINUS_RECT = pg.Rect(450, 240, 34, 34)
INIT_SUN_PLUS_RECT = pg.Rect(500, 240, 34, 34)

_LABEL_FONT_SIZE = 22


def auto_collect_enabled(game_info: dict) -> bool:
    return game_info.get(c.AUTO_COLLECT_SUN) is True


def normalize_custom_init_sun(value: object) -> int:
    """把存档里的初始阳光收成 -1（跟关卡）或 0..SUN_VALUE_CAP。"""
    if isinstance(value, bool):
        return -1
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        return -1
    if value < 0:
        return -1
    return min(value, c.SUN_VALUE_CAP)


def resolve_initial_sun(level_sun: int, game_info: dict) -> int:
    custom_sun = normalize_custom_init_sun(
        game_info.get(c.CUSTOM_INIT_SUN, -1)
    )
    if custom_sun < 0:
        return level_sun
    return custom_sun


def adjust_custom_init_sun(current: int, delta: int) -> int:
    normalized = normalize_custom_init_sun(current)
    if delta > 0:
        if normalized < 0:
            return 0
        return min(normalized + delta, c.SUN_VALUE_CAP)
    if normalized < 0:
        return -1
    updated = normalized + delta
    if updated < 0:
        return -1
    return updated


def format_custom_init_sun(value: int) -> str:
    if value < 0:
        return '默认'
    return str(value)


def _draw_adjust_button(surface: pg.Surface, rect: pg.Rect, sign: str) -> None:
    button = hd.Surface((rect.w, rect.h))
    button.fill((90, 94, 120))
    font = hd.Font(c.FONT_PATH, 28)
    font.bold = True
    glyph = font.render(sign, True, c.YELLOWGREEN)
    glyph_rect = glyph.get_rect(center=button.get_rect().center)
    button.blit(glyph, glyph_rect)
    surface.blit(button, rect)


def draw_sun_options(surface: pg.Surface, game_info: dict) -> None:
    font = hd.Font(c.FONT_PATH, _LABEL_FONT_SIZE)
    if auto_collect_enabled(game_info):
        auto_text = '自动收集：开'
        auto_color = c.YELLOWGREEN
    else:
        auto_text = '自动收集：关'
        auto_color = c.LIGHTGRAY
    auto_image = font.render(auto_text, True, auto_color)
    surface.blit(auto_image, AUTO_COLLECT_TEXT_POS)

    custom_sun = normalize_custom_init_sun(
        game_info.get(c.CUSTOM_INIT_SUN, -1)
    )
    sun_image = font.render(
        f'初始阳光：{format_custom_init_sun(custom_sun)}',
        True,
        c.LIGHTGRAY,
    )
    surface.blit(sun_image, INIT_SUN_TEXT_POS)
    _draw_adjust_button(surface, INIT_SUN_MINUS_RECT, '-')
    _draw_adjust_button(surface, INIT_SUN_PLUS_RECT, '+')


def handle_sun_option_click(
    mouse_pos: Sequence[int], game_info: dict
) -> str | None:
    """点中阳光选项时改 game_info，并返回被修改的键；没点中返回 None。"""
    x, y = mouse_pos
    if AUTO_COLLECT_RECT.collidepoint(x, y):
        game_info[c.AUTO_COLLECT_SUN] = not auto_collect_enabled(game_info)
        return c.AUTO_COLLECT_SUN
    custom_sun = normalize_custom_init_sun(
        game_info.get(c.CUSTOM_INIT_SUN, -1)
    )
    if INIT_SUN_MINUS_RECT.collidepoint(x, y):
        game_info[c.CUSTOM_INIT_SUN] = adjust_custom_init_sun(
            custom_sun, -SUN_ADJUST_STEP
        )
        return c.CUSTOM_INIT_SUN
    if INIT_SUN_PLUS_RECT.collidepoint(x, y):
        game_info[c.CUSTOM_INIT_SUN] = adjust_custom_init_sun(
            custom_sun, SUN_ADJUST_STEP
        )
        return c.CUSTOM_INIT_SUN
    return None
