import csv
import os

from mutagen.flac import FLAC

FOLDERS = [
    r"M:\MusicFlacSource\Secular\_MusicFromCDsFlac",
    r"M:\MusicFlacSource\Christian\_MusicFromCDsFlac",
    r"M:\MusicFlacSource\Classical\MusicFromCDs",
    r"M:\MusicFromCDsRussFlac\_Secular",
    r"M:\MusicFromCDsRussFlac\_Classical",
]

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "list_albums.csv")


def get_flac_tags(album_path):
    """Return (artist, album, year, genre) from the first FLAC file found directly in album_path."""
    try:
        for entry in sorted(os.scandir(album_path), key=lambda e: e.name):
            if entry.is_file() and entry.name.lower().endswith(".flac"):
                audio = FLAC(entry.path)
                artist = (audio.get("albumartist") or audio.get("artist") or [""])[0]
                album  = (audio.get("album") or [""])[0]
                year   = (audio.get("date") or audio.get("year") or [""])[0]
                genre  = (audio.get("genre") or [""])[0]
                return artist, album, year, genre
    except Exception:
        pass
    return "", "", "", ""


with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Folder", "Artist", "Album", "Year", "Genre"])

    for folder in FOLDERS:
        print(f"\n{'='*60}")
        print(f"Folder: {folder}")
        print('='*60)
        if not os.path.exists(folder):
            print("  [Folder not found]")
            continue

        artist_dirs = sorted(
            (e for e in os.scandir(folder) if e.is_dir()),
            key=lambda e: e.name,
        )
        total_albums = 0
        for artist_entry in artist_dirs:
            album_dirs = sorted(
                (e for e in os.scandir(artist_entry.path) if e.is_dir()),
                key=lambda e: e.name,
            )
            if album_dirs:
                for album_entry in album_dirs:
                    artist, album, year, genre = get_flac_tags(album_entry.path)
                    artist = artist or artist_entry.name
                    album  = album  or album_entry.name
                    print(f"  {artist}  |  {album}  [{year}]  [{genre}]")
                    writer.writerow([album_entry.path, artist, album, year, genre])
                    total_albums += 1
            else:
                # No album subdirs — FLAC files sit directly in the artist folder
                artist, album, year, genre = get_flac_tags(artist_entry.path)
                artist = artist or artist_entry.name
                album  = album  or artist_entry.name
                print(f"  {artist}  |  {album}  [{year}]  [{genre}]")
                writer.writerow([artist_entry.path, artist, album, year, genre])
                total_albums += 1

        print(f"\n  Total: {total_albums} album(s)")

print(f"\nResults saved to: {OUTPUT_CSV}")
