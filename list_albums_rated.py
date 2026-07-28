import csv
import os

from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3

FOLDERS = [
	r"M:\Music\Christian\MusicFromCDsFromFlac",
	r"M:\Music\Classical\MusicFromCDsFromFlac",
	r"M:\Music\Secular\MusicFromCDsFromFlac",
	r"M:\MusicFromCDsRussMp3\_Classical",
	r"M:\MusicFromCDsRussMp3\_Secular",
]

FLAC_FOLDERS = [
	r"M:\MusicFlacSource\Christian\_MusicFromCDsFlac",
	r"M:\MusicFlacSource\Classical\MusicFromCDs",
	r"M:\MusicFlacSource\Secular\_MusicFromCDsFlac",
	r"M:\MusicFromCDsRussFlac\_Classical",
	r"M:\MusicFromCDsRussFlac\_Secular",
]

OUTPUT_CSV = os.path.join(
	os.path.dirname(os.path.abspath(__file__)),
	"list_albums_rated.csv",
)

MISMATCH_CSV = os.path.join(
	os.path.dirname(os.path.abspath(__file__)),
	"list_albums_rated_mismatches.csv",
)

UNRESOLVED_CSV = os.path.join(
	os.path.dirname(os.path.abspath(__file__)),
	"list_albums_rated_unresolved.csv",
)


def _first_text(frame):
	if not frame:
		return ""
	text = getattr(frame, "text", None)
	if isinstance(text, list) and text:
		return str(text[0]).strip()
	if isinstance(text, str):
		return text.strip()
	return ""


def _popm_to_stars(popm_value):
	"""Map POPM (0-255) to stars using common MediaMonkey/WMP-style values."""
	if popm_value <= 0:
		return 0
	if popm_value <= 1:
		return 0.5
	if popm_value <= 13:
		return 1.0
	if popm_value <= 54:
		return 1.5
	if popm_value <= 64:
		return 2.0
	if popm_value <= 118:
		return 2.5
	if popm_value <= 128:
		return 3.0
	if popm_value <= 186:
		return 3.5
	if popm_value <= 196:
		return 4.0
	if popm_value <= 242:
		return 4.5
	return 5.0


def _is_rating_txxx(desc):
	"""Only treat explicitly rating-related TXXX fields as ratings."""
	desc_l = (desc or "").strip().lower()
	if not desc_l:
		return False
	if "replaygain" in desc_l:
		return False
	return "rating" in desc_l


def _track_rating(tags):
	"""Return a track rating in stars, or 0 if unrated."""
	if not tags:
		return 0

	# Prefer POPM rating.
	for popm in tags.getall("POPM"):
		rating = getattr(popm, "rating", None)
		if isinstance(rating, int) and rating > 0:
			return _popm_to_stars(rating)

	# Fallback: rating-like TXXX fields only.
	for txxx in tags.getall("TXXX"):
		if not _is_rating_txxx(getattr(txxx, "desc", "")):
			continue
		value = ""
		if getattr(txxx, "text", None):
			value = str(txxx.text[0]).strip()
		if not value:
			continue
		try:
			num = float(value)
		except ValueError:
			continue

		if 0 < num <= 1:
			return round(num * 5, 1)
		if 0 < num <= 5:
			return round(num, 1)
		if 0 < num <= 100:
			return _popm_to_stars(round(num * 255 / 100))
		if 0 < num <= 255:
			return _popm_to_stars(round(num))

	return 0


def _album_rating_from_track_ratings(track_ratings):
	"""Count tracks rated 4.5 to 5 stars."""
	count = sum(1 for r in track_ratings if r >= 4.5)
	return count if count > 0 else ""



def _corresponding_flac_folder(mp3_folder, mp3_root, flac_root):
	relative_path = os.path.relpath(mp3_folder, mp3_root)
	if relative_path == ".":
		candidate = flac_root
		if os.path.exists(candidate):
			return candidate, candidate, "", ""
		return "", candidate, "unresolved", f"No FLAC folder at {candidate}"

	candidate = os.path.join(flac_root, relative_path)
	if os.path.exists(candidate):
		return candidate, candidate, "", ""
	return "", candidate, "unresolved", f"No FLAC folder at {candidate}"


def collect_album_data(album_path, errors):
	artist = ""
	album = ""
	year = ""
	genre = ""
	track_ratings = []

	for root, dirs, files in os.walk(album_path):
		dirs.sort()
		mp3_files = sorted(f for f in files if f.lower().endswith(".mp3"))

		for filename in mp3_files:
			track_path = os.path.join(root, filename)
			try:
				audio = MP3(track_path)
				tags = audio.tags
			except (ID3NoHeaderError, OSError) as ex:
				errors.append(f"Unreadable MP3: {track_path} ({ex})")
				continue

			if not tags:
				continue

			if not artist:
				artist = _first_text(tags.get("TPE2")) or _first_text(tags.get("TPE1"))
			if not album:
				album = _first_text(tags.get("TALB"))
			if not year:
				year = _first_text(tags.get("TDRC")) or _first_text(tags.get("TYER"))
			if not genre:
				genre = _first_text(tags.get("TCON"))

			track_ratings.append(_track_rating(tags))

	album_rating = _album_rating_from_track_ratings(track_ratings)
	return artist, album, year, genre, album_rating


errors = []
mismatches = []
unresolved_pairs = set()

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
	writer = csv.writer(csvfile)
	writer.writerow(["Folder", "FolderFLAC", "Artist", "Album", "Year", "Genre", "Rating5s"])

	for folder, flac_folder in zip(FOLDERS, FLAC_FOLDERS):
		if not os.path.exists(folder):
			errors.append(f"Folder not found: {folder}")
			continue

		artist_dirs = sorted(
			(e for e in os.scandir(folder) if e.is_dir()),
			key=lambda e: e.name,
		)
		for artist_entry in artist_dirs:
			album_dirs = sorted(
				(e for e in os.scandir(artist_entry.path) if e.is_dir()),
				key=lambda e: e.name,
			)

			if album_dirs:
				for album_entry in album_dirs:
					artist, album, year, genre, rating = collect_album_data(album_entry.path, errors)
					artist = artist or artist_entry.name
					album = album or album_entry.name
					folder_flac, expected_folder_flac, mismatch_status, mismatch_details = _corresponding_flac_folder(album_entry.path, folder, flac_folder)
					if mismatch_status:
						mismatches.append([album_entry.path, folder_flac, expected_folder_flac, mismatch_status, mismatch_details])
					if mismatch_status in {"unresolved", "ambiguous"}:
						unresolved_pairs.add((artist, album))
					writer.writerow([album_entry.path, folder_flac, artist, album, year, genre, rating])
			else:
				artist, album, year, genre, rating = collect_album_data(artist_entry.path, errors)
				artist = artist or artist_entry.name
				album = album or artist_entry.name
				folder_flac, expected_folder_flac, mismatch_status, mismatch_details = _corresponding_flac_folder(artist_entry.path, folder, flac_folder)
				if mismatch_status:
					mismatches.append([artist_entry.path, folder_flac, expected_folder_flac, mismatch_status, mismatch_details])
				if mismatch_status in {"unresolved", "ambiguous"}:
					unresolved_pairs.add((artist, album))
				writer.writerow([artist_entry.path, folder_flac, artist, album, year, genre, rating])

with open(MISMATCH_CSV, "w", newline="", encoding="utf-8") as csvfile:
	writer = csv.writer(csvfile)
	writer.writerow(["Folder", "FolderFLAC", "ExpectedFolderFLAC", "Status", "Details"])
	writer.writerows(mismatches)

with open(UNRESOLVED_CSV, "w", newline="", encoding="utf-8") as csvfile:
	writer = csv.writer(csvfile)
	writer.writerow(["Artist", "Album"])
	writer.writerows(sorted(unresolved_pairs, key=lambda pair: (pair[0].casefold(), pair[1].casefold())))

for error in errors:
	print(error)

print(f"Mismatch report saved to: {MISMATCH_CSV}")
print(f"Unresolved cleanup list saved to: {UNRESOLVED_CSV}")
