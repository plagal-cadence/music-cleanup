"""Cached Spotify lookups used to corroborate artist names.

Uses the Client Credentials flow: this only ever reads public catalogue data, so
no browser round trip, no redirect URI and no user scope are needed. Every
response is cached on disk so repeat runs and re-reviews cost no API calls.
"""

import json
import os
import sys
from pathlib import Path

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:
    print(
        "This process requires spotipy. Install it with: python -m pip install spotipy",
        file=sys.stderr,
    )
    raise

from tags import normalize, similarity

# Same app credentials as the scripts in D:\Code\spotify; override with env vars.
DEFAULT_CLIENT_ID = "4dea019c667e4497b67c70926d728625"
DEFAULT_CLIENT_SECRET = "7ad394b030114117b0a11cc794454301"
CACHE_VERSION = 1


class SpotifyLookup:
    def __init__(self, cache_path: Path, offline: bool = False) -> None:
        self.cache_path = cache_path
        self.offline = offline
        self.hits = 0
        self.calls = 0
        self._dirty = False
        self._cache: dict[str, object] = {}
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if payload.get("version") == CACHE_VERSION:
                    self._cache = payload.get("entries", {})
            except (OSError, ValueError):
                self._cache = {}
        self._client: spotipy.Spotify | None = None

    @property
    def client(self) -> spotipy.Spotify:
        if self._client is None:
            self._client = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=os.environ.get("SPOTIPY_CLIENT_ID", DEFAULT_CLIENT_ID),
                    client_secret=os.environ.get(
                        "SPOTIPY_CLIENT_SECRET", DEFAULT_CLIENT_SECRET
                    ),
                ),
                requests_timeout=20,
                retries=5,
            )
        return self._client

    def save(self) -> None:
        if not self._dirty:
            return
        payload = {"version": CACHE_VERSION, "entries": self._cache}
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=True), encoding="utf-8"
        )
        self._dirty = False

    def _cached(self, key: str, produce) -> object:
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        if self.offline:
            return None
        try:
            value = produce()
        except Exception as error:  # network/auth/rate-limit: cache nothing, degrade
            print(f"\nSpotify lookup failed ({key}): {error}", file=sys.stderr)
            return None
        self.calls += 1
        self._cache[key] = value
        self._dirty = True
        if self.calls % 25 == 0:
            self.save()
        return value

    # ---- primitive queries -------------------------------------------------

    def search_tracks(self, query: str, limit: int = 8) -> list[dict]:
        """Return simplified track hits for a raw Spotify query string."""
        payload = self._cached(
            f"track\x00{limit}\x00{query}",
            lambda: [
                {
                    "title": item["name"],
                    "artists": [artist["name"] for artist in item["artists"]],
                    "album": item["album"]["name"],
                    "album_artists": [
                        artist["name"] for artist in item["album"]["artists"]
                    ],
                    "popularity": item.get("popularity", 0),
                }
                for item in self.client.search(q=query, type="track", limit=limit)[
                    "tracks"
                ]["items"]
            ],
        )
        return payload or []

    def search_albums(self, name: str, limit: int = 8) -> list[dict]:
        payload = self._cached(
            f"album\x00{limit}\x00{name}",
            lambda: [
                {"id": item["id"], "name": item["name"], "total": item["total_tracks"]}
                for item in self.client.search(
                    q=f'album:"{name}"', type="album", limit=limit
                )["albums"]["items"]
            ],
        )
        return payload or []

    def album_tracks(self, album_id: str) -> list[dict]:
        def produce() -> list[dict]:
            collected = []
            page = self.client.album_tracks(album_id, limit=50)
            while page:
                collected.extend(
                    {
                        "title": item["name"],
                        "artists": [artist["name"] for artist in item["artists"]],
                        "track": item.get("track_number", 0),
                        "disc": item.get("disc_number", 1),
                    }
                    for item in page["items"]
                )
                page = self.client.next(page) if page.get("next") else None
            return collected

        payload = self._cached(f"album_tracks\x00{album_id}", produce)
        return payload or []

    def artist_exists(self, name: str) -> dict | None:
        """Confirm a candidate string is a real artist, returning the best match."""
        candidate = name.strip()
        if len(normalize(candidate)) < 3:
            return None
        payload = self._cached(
            f"artist\x00{candidate}",
            lambda: [
                {
                    "name": item["name"],
                    "popularity": item.get("popularity", 0),
                    "genres": item.get("genres", []),
                    "followers": item.get("followers", {}).get("total", 0),
                }
                for item in self.client.search(
                    q=f'artist:"{candidate}"', type="artist", limit=5
                )["artists"]["items"]
            ],
        )
        if not payload:
            return None
        wanted = normalize(candidate)
        best = None
        best_score = 0.0
        for item in payload:
            score = similarity(candidate, item["name"])
            # "Bach" -> "Johann Sebastian Bach": a surname match is real evidence.
            # Matching on any token would wrongly accept "Love" -> "Love Kills",
            # so only the final token counts.
            tokens = [normalize(word) for word in item["name"].split() if normalize(word)]
            if len(wanted) >= 4 and tokens and wanted == tokens[-1]:
                score = max(score, 0.92)
            if score > best_score:
                best, best_score = item, score
        if best is None or best_score < 0.85:
            return None
        return {**best, "match": best_score}


__all__ = ["SpotifyLookup"]
