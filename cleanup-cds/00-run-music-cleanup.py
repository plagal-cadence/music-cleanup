"""Run the complete FLAC-to-MP3 reconciliation workflow.

The workflow is report-only and does not copy staged MP3 files.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parent
PROJECT_ROOT = WORKSPACE.parent
PROJECT_PYTHON = PROJECT_ROOT / '.venv' / 'Scripts' / 'python.exe'
DEFAULT_MP3_ROOTS = [
    r'M:\Music\Christian\MusicFromCDsFromFlac',
    r'M:\Music\Classical\MusicFromCDsFromFlac',
    r'M:\Music\Secular\MusicFromCDsFromFlac',
    r'M:\MusicFromCDsRussMp3\_Classical',
    r'M:\MusicFromCDsRussMp3\_Secular',
]


def run_step(label, script, arguments=()):
    python_executable = PROJECT_PYTHON if PROJECT_PYTHON.exists() else Path(sys.executable)
    command = [str(python_executable), str(WORKSPACE / script), *arguments]
    print(f'\n=== {label} ===')
    subprocess.run(command, cwd=WORKSPACE, check=True)


def main():
    parser = argparse.ArgumentParser(description='Run the complete music cleanup reconciliation workflow')
    parser.add_argument(
        '--mp3-root',
        action='append',
        dest='mp3_roots',
        help='MP3 root to search; repeat for multiple roots. Defaults to the configured M: roots.',
    )
    parser.add_argument('--top', type=int, default=5, help='Fuzzy candidates per unresolved track')
    args = parser.parse_args()

    mp3_roots = args.mp3_roots or DEFAULT_MP3_ROOTS
    mapper_arguments = []
    for root in mp3_roots:
        mapper_arguments.extend(['--mp3-root', root])
    mapper_arguments.extend(['--top', str(args.top)])

    run_step('Inventory FLAC albums', '01-inventory.py')
    run_step('Map FLAC tracks to MP3s', '02-mapping.py', mapper_arguments)
    run_step('Write complete missing-track report', '03-missing-track-report.py')
    run_step('Write missing-track album summary', '04-album-summary.py')
    run_step('Create missing FLAC playlist', '05-playlist.py')
    run_step('Write track-level path analysis', '06-track-analysis.py')

    print('\nWorkflow completed.')
    print('No music files were modified.')


if __name__ == '__main__':
    main()
