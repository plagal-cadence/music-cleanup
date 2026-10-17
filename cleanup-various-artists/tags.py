"""Shared tag reading, tag writing, and string comparison helpers."""

import sys
from difflib import SequenceMatcher
from pathlib import Path

try:
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, TALB, TIT2, TPE1, TPE2, ID3NoHeaderError
    from mutagen.mp3 import MP3
except ImportError:
    print(
        "This process requires mutagen. Install it with: python -m pip install mutagen",
        file=sys.stderr,
    )
    raise


VARIOUS_VALUES = {"various", "variousartists"}


def use_utf8_stdout() -> None:
    """Windows consoles default to cp1252 and crash on accented track titles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def progress(current: int, total: int, label: str) -> None:
    percent = current / total if total else 1
    filled = int(40 * percent)
    line = f"{label} [{'#' * filled}{'-' * (40 - filled)}] {percent:6.1%} ({current}/{total})"
    if sys.stdout.isatty():
        print(f"\r{line}", end="", flush=True)
    else:
        print(line, flush=True)


def normalize(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def similarity(left: str, right: str) -> float:
    left_normalized = normalize(left)
    right_normalized = normalize(right)
    if not left_normalized or not right_normalized:
        return 0.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def fuzzy_same(left: str, right: str, threshold: float = 0.9) -> bool:
    return similarity(left, right) >= threshold


def is_various(value: str) -> bool:
    return normalize(value) in VARIOUS_VALUES


def _flac_first(audio: FLAC, name: str) -> str:
    values = audio.get(name) or []
    return str(values[0]).strip() if values else ""


def _id3_first(tags: ID3 | None, name: str) -> str:
    if tags is None:
        return ""
    frame = tags.get(name)
    text = getattr(frame, "text", None)
    if not text:
        return ""
    return str(text[0]).strip()


def read_audio_tags(file_path: Path) -> dict[str, str]:
    """Return artist/album_artist/title/album/track for a FLAC or MP3 file."""
    if file_path.suffix.casefold() == ".mp3":
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = None
        return {
            "artist": _id3_first(tags, "TPE1"),
            "album_artist": _id3_first(tags, "TPE2"),
            "title": _id3_first(tags, "TIT2"),
            "album": _id3_first(tags, "TALB"),
            "track": _id3_first(tags, "TRCK"),
        }
    audio = FLAC(file_path)
    try:
        return {
            "artist": _flac_first(audio, "artist"),
            "album_artist": _flac_first(audio, "albumartist"),
            "title": _flac_first(audio, "title"),
            "album": _flac_first(audio, "album"),
            "track": _flac_first(audio, "tracknumber"),
        }
    finally:
        file_object = getattr(audio, "fileobj", None)
        if file_object is not None:
            file_object.close()


def write_tags(file_path: Path, artist: str | None = None, title: str | None = None) -> None:
    """Set Artist and/or Title, leaving Album Artist and everything else alone.

    Passing None for a field skips it, so a title-only correction never rewrites
    an artist that is already right.
    """
    if artist is None and title is None:
        return
    if file_path.suffix.casefold() == ".mp3":
        audio = MP3(file_path)
        if audio.tags is None:
            audio.add_tags()
        if artist is not None:
            audio.tags.setall("TPE1", [TPE1(encoding=3, text=[artist])])
        if title is not None:
            audio.tags.setall("TIT2", [TIT2(encoding=3, text=[title])])
        audio.save(v2_version=3)
        return
    audio = FLAC(file_path)
    if artist is not None:
        audio["artist"] = [artist]
    if title is not None:
        audio["title"] = [title]
    audio.save()


def write_album(file_path: Path, album: str) -> None:
    """Set Album, leaving Artist, Album Artist and Title alone."""
    if file_path.suffix.casefold() == ".mp3":
        audio = MP3(file_path)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.setall("TALB", [TALB(encoding=3, text=[album])])
        audio.save(v2_version=3)
        return
    audio = FLAC(file_path)
    audio["album"] = [album]
    audio.save()


def read_album_artist(file_path: Path) -> str:
    return read_audio_tags(file_path)["album_artist"]


__all__ = [
    "FLAC",
    "ID3",
    "MP3",
    "TALB",
    "TIT2",
    "TPE1",
    "TPE2",
    "VARIOUS_VALUES",
    "fuzzy_same",
    "is_various",
    "normalize",
    "progress",
    "read_album_artist",
    "read_audio_tags",
    "similarity",
    "use_utf8_stdout",
    "write_album",
    "write_tags",
]
