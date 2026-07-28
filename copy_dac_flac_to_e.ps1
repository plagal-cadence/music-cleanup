$ErrorActionPreference = 'Stop'

$mdPath = 'D:\Code\dac_comparison.md'
$destRoot = 'E:\DAC_Comparison_FLAC'
$csvPaths = @('D:\Code\list_albums_rated.csv', 'D:\Code\list_albums.csv')

function Normalize([string]$s) {
  if ([string]::IsNullOrWhiteSpace($s)) { return '' }
  return (($s.ToLowerInvariant()) -replace '[^a-z0-9]', '')
}

New-Item -Path $destRoot -ItemType Directory -Force | Out-Null

$index = @{}
foreach ($csv in $csvPaths) {
  if (-not (Test-Path $csv)) { continue }
  foreach ($r in (Import-Csv $csv)) {
    if (-not $r.Artist -or -not $r.Album) { continue }

    $folder = $null
    if ($r.PSObject.Properties.Name -contains 'FolderFLAC' -and $r.FolderFLAC) {
      $folder = $r.FolderFLAC
    } elseif ($r.Folder) {
      $folder = $r.Folder
    }
    if (-not $folder) { continue }

    $key = (Normalize $r.Artist) + '|' + (Normalize $r.Album)
    if (-not $index.ContainsKey($key)) { $index[$key] = $folder }
  }
}

$tracks = @()
foreach ($line in Get-Content $mdPath) {
  if ($line -match '^\|\s*\d+\s*\|') {
    $parts = $line.Split('|')
    if ($parts.Count -ge 8) {
      $artist = $parts[2].Trim()
      $album = $parts[3].Trim().Trim('*')
      $track = $parts[4].Trim().Trim('*')
      if ($artist -and $album -and $track) {
        $tracks += [pscustomobject]@{
          Artist = $artist
          Album = $album
          Track = $track
        }
      }
    }
  }
}

$copied = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]

foreach ($t in $tracks) {
  $key = (Normalize $t.Artist) + '|' + (Normalize $t.Album)
  $folder = $null

  if ($index.ContainsKey($key)) {
    $folder = $index[$key]
  } else {
    $albumNorm = Normalize $t.Album
    $fallback = $index.GetEnumerator() |
      Where-Object { $_.Key -like "*|$albumNorm" } |
      Select-Object -First 1
    if ($fallback) { $folder = $fallback.Value }
  }

  if (-not $folder -or -not (Test-Path $folder)) {
    $missing.Add("NO ALBUM FOLDER :: $($t.Artist) | $($t.Album) | $($t.Track)")
    continue
  }

  $trackNorm = Normalize $t.Track
  $files = Get-ChildItem -Path $folder -File -Filter '*.flac' -ErrorAction SilentlyContinue
  if (-not $files -or $files.Count -eq 0) {
    $missing.Add("NO FLAC FILES :: $($t.Artist) | $($t.Album) | $($t.Track)")
    continue
  }

  $match = $files |
    Where-Object { (Normalize $_.BaseName) -like "*$trackNorm*" } |
    Select-Object -First 1

  if (-not $match) {
    $missing.Add("NO TRACK MATCH :: $($t.Artist) | $($t.Album) | $($t.Track)")
    continue
  }

  $safeArtist = $t.Artist -replace '[\\/:*?"<>|]', '_'
  $safeAlbum = $t.Album -replace '[\\/:*?"<>|]', '_'
  $outDir = Join-Path $destRoot ("$safeArtist - $safeAlbum")
  New-Item -Path $outDir -ItemType Directory -Force | Out-Null

  $outFile = Join-Path $outDir $match.Name
  Copy-Item -Path $match.FullName -Destination $outFile -Force
  $copied.Add("$($match.FullName) -> $outFile")
}

$reportPath = Join-Path $destRoot 'copy_report.txt'
@(
  "Copied: $($copied.Count)",
  "Missing: $($missing.Count)",
  '',
  '--- COPIED ---'
) + $copied + @(
  '',
  '--- MISSING ---'
) + $missing | Set-Content -Path $reportPath

Write-Output "Destination: $destRoot"
Write-Output "Copied: $($copied.Count)"
Write-Output "Missing: $($missing.Count)"
Write-Output "Report: $reportPath"
