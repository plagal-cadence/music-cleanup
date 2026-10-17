"""FLAC source roots and the MP3 destinations they were converted into."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RootMapping:
    flac_sources: tuple[Path, ...]
    mp3_destinations: tuple[Path, ...]


ROOT_MAPPINGS = [
    # Classical from CDs
    RootMapping(
        flac_sources=(
            Path(r"M:\MusicFlacSource\Secular\_MusicFromCDsFlac"),
        ),
        mp3_destinations=(
            Path(r"M:\Music\Secular\MusicFromCDsFromFlac"),
        ),
    ),
    RootMapping(
        flac_sources=(Path(r"M:\MusicFlacSource\Christian\_MusicFromCDsFlac"),),
        mp3_destinations=(Path(r"M:\Music\Christian\MusicFromCDsFromFlac"),),
    ),
    RootMapping(
        flac_sources=(
            Path(r"M:\MusicFlacSource\Classical\MusicFromCDs"),
        ),
        mp3_destinations=(
            Path(r"M:\Music\Classical\MusicFromCDsFromFlac"),
        ),
    ),
]
