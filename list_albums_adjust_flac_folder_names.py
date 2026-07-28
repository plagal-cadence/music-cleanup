import argparse
import csv
import os


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
	"list_albums_adjust_flac_folder_names.csv",
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


def find_matching_flac_path(mp3_album_path, mp3_root, flac_root):
	relative_path = os.path.relpath(mp3_album_path, mp3_root)
	if relative_path == ".":
		candidate = flac_root
		return candidate if os.path.exists(candidate) else ""

	candidate = os.path.join(flac_root, relative_path)
	return candidate if os.path.exists(candidate) else ""


def planned_renames():
	for mp3_root, flac_root in ROOT_PAIRS:
		for artist_name, album_name, mp3_album_path in collect_album_dirs(mp3_root):
			flac_album_path = find_matching_flac_path(mp3_album_path, mp3_root, flac_root)
			if not flac_album_path:
				continue

			current_name = os.path.basename(flac_album_path)
			if current_name == album_name:
				continue

			target_path = os.path.join(os.path.dirname(flac_album_path), album_name)
			yield {
				"artist": artist_name,
				"album": album_name,
				"mp3_root": mp3_root,
				"flac_root": flac_root,
				"mp3_album_path": mp3_album_path,
				"flac_album_path": flac_album_path,
				"target_path": target_path,
				"current_name": current_name,
				"target_name": album_name,
			}


def write_plans_csv(plans):
	with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
		writer = csv.writer(csvfile)
		writer.writerow([
			"Artist",
			"Album",
			"Mp3Root",
			"FlacRoot",
			"Mp3AlbumPath",
			"FlacAlbumPath",
			"CurrentName",
			"TargetName",
			"TargetPath",
		])
		for plan in plans:
			writer.writerow([
				plan["artist"],
				plan["album"],
				plan["mp3_root"],
				plan["flac_root"],
				plan["mp3_album_path"],
				plan["flac_album_path"],
				plan["current_name"],
				plan["target_name"],
				plan["target_path"],
			])


def apply_renames(apply_changes):
	plans = list(planned_renames())
	write_plans_csv(plans)
	if not plans:
		print(f"CSV saved to: {OUTPUT_CSV}")
		print("No FLAC folder renames needed.")
		return 0

	renamed = 0
	skipped = 0
	for plan in plans:
		if os.path.exists(plan["target_path"]):
			print(f"SKIP exists: {plan['flac_album_path']} -> {plan['target_path']}")
			skipped += 1
			continue

		print(f"RENAME {plan['flac_album_path']} -> {plan['target_path']}")
		if apply_changes:
			os.rename(plan["flac_album_path"], plan["target_path"])
			renamed += 1

	print()
	print(f"Planned: {len(plans)}")
	print(f"Renamed: {renamed}")
	print(f"Skipped: {skipped}")
	print(f"CSV saved to: {OUTPUT_CSV}")
	if not apply_changes:
		print("Dry run only. Re-run with --apply to rename folders.")
	return 0


def main():
	parser = argparse.ArgumentParser(
		description="Rename FLAC album folders to match MP3 album folder names.",
	)
	parser.add_argument(
		"--apply",
		action="store_true",
		help="Apply the renames. Without this flag, only print the planned changes.",
	)
	args = parser.parse_args()
	return apply_renames(args.apply)


if __name__ == "__main__":
	raise SystemExit(main())