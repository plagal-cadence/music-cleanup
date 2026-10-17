import csv
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
mapping_path = WORKSPACE / '03-missing-track-report.csv'
playlist_path = WORKSPACE / '05-playlist.m3u'

track_paths = []
with open(mapping_path, newline='', encoding='utf-8') as mapping_file:
    reader = csv.DictReader(mapping_file)
    for row in reader:
        track_paths.append(f"{row['flac_album']}\\{row['flac_track']}")

with open(playlist_path, 'w', encoding='utf-8', newline='') as playlist_file:
    playlist_file.write('#EXTM3U\n')
    playlist_file.write('\n'.join(track_paths))
    playlist_file.write('\n')

print(f'Wrote {playlist_path}')
print(f'Playlist entries: {len(track_paths)}')
