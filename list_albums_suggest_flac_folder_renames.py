import csv
import difflib
import os
import re


ROOT_PAIRS = [
	(
		r"M:\Music\Christian\MusicFromCDsFromFlac",
		r"M:\MusicFlacSource\Christian\_MusicFromCDsFlac",
	),
	(
		r"M:\Music\Classical\MusicFromCDsFromFlac",
		r"M:\MusicFlacSource\Classical\MusicFromCDs",
	),
	(
		r"M:\Music\Secular\MusicFromCDsFromFlac",
		r"M:\MusicFlacSource\Secular\_MusicFromCDsFlac",
	),
	(
		r"M:\MusicFromCDsRussMp3\_Classical",
		r"M:\MusicFromCDsRussFlac\_Classical",
	),
	(
		r"M:\MusicFromCDsRussMp3\_Secular",
		r"M:\MusicFromCDsRussFlac\_Secular",
	),
]

OUTPUT_CSV = os.path.join(
	os.path.dirname(os.path.abspath(__file__)),
	"list_albums_suggest_flac_folder_renames.csv",
)


def has_mp3_files(folder_path):
	for root, _, files in os.walk(folder_path):
		for filename in files:
			if filename.lower().endswith(".mp3"):
				return True
	return False


def collect_album_dirs(root_folder):
	if not os.path.exists(root_folder):
		return []

	album_dirs = []
	artist_dirs = sorted(
		(entry for entry in os.scandir(root_folder) if entry.is_dir()),
		key=lambda entry: entry.name.casefold(),
	)
	for artist_entry in artist_dirs:
		child_dirs = sorted(
			(entry for entry in os.scandir(artist_entry.path) if entry.is_dir()),
			key=lambda entry: entry.name.casefold(),
		)
		if child_dirs:
			for album_entry in child_dirs:
				if has_mp3_files(album_entry.path):
					album_dirs.append((artist_entry.name, album_entry.name, album_entry.path))
		else:
			if has_mp3_files(artist_entry.path):
				album_dirs.append((artist_entry.name, artist_entry.name, artist_entry.path))
	return album_dirs


def normalize_name(name):
	name = (name or "").casefold().strip()
	name = re.sub(r"\([^)]*\)", " ", name)
	name = re.sub(r"\bdisc\b", "disk", name)
	name = re.sub(r"[^a-z0-9]+", " ", name)
	name = re.sub(r"\s+", " ", name)
	return name.strip()


def best_sibling_match(target_name, child_dirs):
	normalized_target = normalize_name(target_name)
	if not normalized_target:
		return None

	best_entry = None
	best_score = 0.0
	second_best_score = 0.0
	best_basis = ""

	for entry in child_dirs:
		normalized_candidate = normalize_name(entry.name)
		if not normalized_candidate:
			continue

		if normalized_candidate == normalized_target:
			score = 1.0
			basis = "normalized sibling folder name match"
		elif normalized_target in normalized_candidate or normalized_candidate in normalized_target:
			score = 0.92
			basis = "normalized sibling contains target"
		else:
			score = difflib.SequenceMatcher(None, normalized_target, normalized_candidate).ratio()
			basis = "similar sibling folder name"

		if score > best_score:
			second_best_score = best_score
			best_entry = entry
			best_score = score
			best_basis = basis
		elif score > second_best_score:
			second_best_score = score

	if best_entry is None:
		return None
	if best_score < 0.84:
		return None
	if best_score - second_best_score < 0.08 and best_score < 1.0:
		return None

	return best_entry, best_score, best_basis


def exact_flac_path(mp3_album_path, mp3_root, flac_root):
	relative_path = os.path.relpath(mp3_album_path, mp3_root)
	if relative_path == ".":
		candidate = flac_root
	else:
		candidate = os.path.join(flac_root, relative_path)
	return candidate if os.path.exists(candidate) else ""


def suggest_renames():
	for mp3_root, flac_root in ROOT_PAIRS:
		for artist_name, album_name, mp3_album_path in collect_album_dirs(mp3_root):
			if exact_flac_path(mp3_album_path, mp3_root, flac_root):
				continue

			relative_path = os.path.relpath(mp3_album_path, mp3_root)
			parent_relative = os.path.dirname(relative_path)
			target_name = os.path.basename(relative_path)
			flac_parent = flac_root if parent_relative in ("", ".") else os.path.join(flac_root, parent_relative)
			if not os.path.exists(flac_parent):
				continue

			try:
				child_dirs = sorted(
					(entry for entry in os.scandir(flac_parent) if entry.is_dir()),
					key=lambda entry: entry.name.casefold(),
				)
			except OSError:
				continue

			match_info = best_sibling_match(target_name, child_dirs)
			if match_info is None:
				continue

			match, score, basis = match_info
			target_path = os.path.join(flac_parent, target_name)
			if match.path == target_path:
				continue

			yield {
				"artist": artist_name,
				"album": album_name,
				"mp3_root": mp3_root,
				"flac_root": flac_root,
				"mp3_album_path": mp3_album_path,
				"flac_parent": flac_parent,
				"suggested_flac_path": match.path,
				"current_name": match.name,
				"target_name": target_name,
				"target_path": target_path,
				"basis": basis,
				"score": f"{score:.3f}",
			}


def write_suggestions_csv(suggestions):
	with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
		writer = csv.writer(csvfile)
		writer.writerow([
			"Artist",
			"Album",
			"Mp3Root",
			"FlacRoot",
			"Mp3AlbumPath",
			"FlacParent",
			"SuggestedFlacPath",
			"CurrentName",
			"TargetName",
			"TargetPath",
			"Basis",
			"Score",
		])
		for item in suggestions:
			writer.writerow([
				item["artist"],
				item["album"],
				item["mp3_root"],
				item["flac_root"],
				item["mp3_album_path"],
				item["flac_parent"],
				item["suggested_flac_path"],
				item["current_name"],
				item["target_name"],
				item["target_path"],
				item["basis"],
				item["score"],
			])


def main():
	suggestions = list(suggest_renames())
	write_suggestions_csv(suggestions)
	print(f"CSV saved to: {OUTPUT_CSV}")
	print(f"Suggestions: {len(suggestions)}")
	for item in suggestions:
		print(f"SUGGEST {item['suggested_flac_path']} -> {item['target_path']}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())