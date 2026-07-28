$ErrorActionPreference = 'Stop'

$mdPath = 'D:\Code\dac_comparison.md'
$csvPaths = @('D:\Code\list_albums_rated.csv', 'D:\Code\list_albums.csv')
$destRoot = 'E:\'

function Normalize([string]$s) {
  if ([string]::IsNullOrWhiteSpace($s)) { return '' }
  return (($s.ToLowerInvariant()) -replace '[^a-z0-9]', '')
}

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
  if ($line -match '^\|\s*(\d+)\s*\|') {
    $parts = $line.Split('|')
    if ($parts.Count -ge 8) {
      $n = [int]$parts[1].Trim()
      $artist = $parts[2].Trim()
      $album = $parts[3].Trim().Trim('*')
      $track = $parts[4].Trim().Trim('*')
      if ($artist -and $album -and $track) {
        $tracks += [pscustomobject]@{
          Number = $n
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

foreach ($t in ($tracks | Sort-Object Number)) {
  $albumKey = (Normalize $t.Artist) + '|' + (Normalize $t.Album)
  $folder = $null

  if ($index.ContainsKey($albumKey)) {
    $folder = $index[$albumKey]
  } else {
    $albumNorm = Normalize $t.Album
    $fallback = $index.GetEnumerator() |
      Where-Object { $_.Key -like "*|$albumNorm" } |
      Select-Object -First 1
    if ($fallback) { $folder = $fallback.Value }
  }

  if (-not $folder -or -not (Test-Path $folder)) {
    $missing.Add("NO ALBUM FOLDER :: $($t.Number) | $($t.Artist) | $($t.Album) | $($t.Track)")
    continue
  }

  $trackNorm = Normalize $t.Track
  $files = Get-ChildItem -Path $folder -File -Filter '*.flac' -ErrorAction SilentlyContinue
  if (-not $files -or $files.Count -eq 0) {
    $missing.Add("NO FLAC FILES :: $($t.Number) | $($t.Artist) | $($t.Album) | $($t.Track)")
    continue
  }

  $match = $files |
    Where-Object { (Normalize $_.BaseName) -like "*$trackNorm*" } |
    Select-Object -First 1

  if (-not $match) {
    if ($t.Artist -eq 'Johnny Clegg & Savuka' -and $t.Track -eq 'Asimbonanga') {
      $altFolder = 'M:\MusicFlacSource\Secular\_MusicFromCDsFlac\Johnny Clegg & Savuka\Third World Child'
      if (Test-Path $altFolder) {
        $match = Get-ChildItem -Path $altFolder -File -Filter '*.flac' |
          Where-Object { (Normalize $_.BaseName) -like '*asimbonanga*' } |
          Select-Object -First 1
      }
    }

    if (-not $match -and $t.Artist -eq 'UB40' -and $t.Track -eq 'Rat in Mi Kitchen') {
      $match = $files |
        Where-Object { (Normalize $_.BaseName) -like '*ratinmekitchen*' } |
        Select-Object -First 1
    }
  }

  if (-not $match) {
    $missing.Add("NO TRACK MATCH :: $($t.Number) | $($t.Artist) | $($t.Album) | $($t.Track)")
    continue
  }

  $safeArtist = $t.Artist -replace '[\\/:*?"<>|]', '_'
  $safeAlbum = $t.Album -replace '[\\/:*?"<>|]', '_'
  $safeTrackBase = $match.BaseName -replace '[\\/:*?"<>|]', '_'
  $fileName = ('{0:D2} - {1} - {2} - {3}.flac' -f $t.Number, $safeArtist, $safeAlbum, $safeTrackBase)
  $destPath = Join-Path $destRoot $fileName

  Copy-Item -Path $match.FullName -Destination $destPath -Force
  $copied.Add($destPath)
}

Write-Output "Copied: $($copied.Count)"
Write-Output "Missing: $($missing.Count)"
if ($missing.Count -gt 0) {
  $missing | ForEach-Object { Write-Output $_ }
}
