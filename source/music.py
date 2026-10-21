"""Deadlock-safe wrappers around pygame.mixer.music.

pygame-ce's music.pause/unpause/set_volume/stop call SDL_mixer while still
holding the GIL, and those SDL_mixer functions take the SDL audio lock. When a
sound effect finishes, the audio thread holds the audio lock and calls back
into Python (pygame's channel-finished callback needs the GIL). If both happen
at once the game freezes forever. ctypes releases the GIL around foreign calls,
so calling SDL_mixer directly through ctypes breaks the cycle.
"""

import ctypes
import glob
import logging
import os

import pygame as pg

logger = logging.getLogger('main')

_MIX_MAX_VOLUME = 128


def _loadMixerLib() -> ctypes.CDLL | None:
    pg_dir = os.path.dirname(pg.__file__)
    # macOS wheel: pygame/.dylibs, Linux wheel: pygame_ce.libs, Windows: pygame/
    patterns = (
        os.path.join(pg_dir, '.dylibs', '*SDL2_mixer*'),
        os.path.join(os.path.dirname(pg_dir), 'pygame_ce.libs', '*SDL2_mixer*'),
        os.path.join(pg_dir, '*SDL2_mixer*'),
    )
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                lib = ctypes.CDLL(path)
            except OSError:
                continue
            lib.Mix_PauseMusic.restype = None
            lib.Mix_ResumeMusic.restype = None
            lib.Mix_HaltMusic.restype = ctypes.c_int
            lib.Mix_VolumeMusic.argtypes = (ctypes.c_int,)
            lib.Mix_VolumeMusic.restype = ctypes.c_int
            return lib
    logger.warning('SDL2_mixer not found, falling back to pygame.mixer.music')
    return None


_lib = _loadMixerLib()


def pause() -> None:
    if _lib is None:
        pg.mixer.music.pause()
    else:
        _lib.Mix_PauseMusic()


def unpause() -> None:
    if _lib is None:
        pg.mixer.music.unpause()
    else:
        _lib.Mix_ResumeMusic()


def stop() -> None:
    if _lib is None:
        pg.mixer.music.stop()
    else:
        _lib.Mix_HaltMusic()


def set_volume(volume: float) -> None:
    if _lib is None:
        pg.mixer.music.set_volume(volume)
    else:
        _lib.Mix_VolumeMusic(int(max(0.0, min(volume, 1.0)) * _MIX_MAX_VOLUME))
