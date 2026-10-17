import csv
from collections import defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent
inp = WORKSPACE / '02-mapping.csv'
out = WORKSPACE / '04-album-summary.csv'

albums = defaultdict(list)
with open(inp, newline='', encoding='utf-8') as f:
    r = csv.reader(f)
    header = next(r, None)
    for row in r:
        if len(row) < 4:
            continue
        album = row[0]
        flac_track = row[1]
        mp3_found = row[2].strip().lower()
        candidates = row[3]
        if mp3_found != 'yes':
            albums[album].append((flac_track, candidates))

with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['album','missing_count','sample_missing'])
    for album, items in sorted(albums.items(), key=lambda t: -len(t[1])):
        # sample up to 5 missing tracks with their candidate strings
        sample = []
        for flac, cand in items[:5]:
            sample.append(f"{flac} -> {cand}")
        sample_str = ' || '.join(sample)
        w.writerow([album, len(items), sample_str])

print('Wrote', out)
