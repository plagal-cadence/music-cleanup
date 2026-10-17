import csv
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
mapping_path = WORKSPACE / '02-mapping.csv'
missing_csv_path = WORKSPACE / '03-missing-track-report.csv'

missing_by_album = defaultdict(list)
total_tracks = 0

with open(mapping_path, newline='', encoding='utf-8') as mapping_file:
    reader = csv.DictReader(mapping_file)
    for row in reader:
        total_tracks += 1
        if row['mp3_found'].strip().lower() == 'yes':
            continue
        missing_by_album[row['flac_album']].append(row)

missing_rows = [
    row
    for album in sorted(missing_by_album)
    for row in missing_by_album[album]
]

with open(missing_csv_path, 'w', newline='', encoding='utf-8') as output_file:
    writer = csv.DictWriter(
        output_file,
        fieldnames=['flac_album', 'flac_track', 'mp3_found', 'mp3_path_or_candidates'],
    )
    writer.writeheader()
    writer.writerows(missing_rows)

print(f'Total FLAC tracks inspected: {total_tracks}')
print(f'Missing MP3 tracks: {len(missing_rows)}')
print(f'Albums with missing tracks: {len(missing_by_album)}')
print(f'Wrote {missing_csv_path}')
