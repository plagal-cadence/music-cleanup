param(
    [string]$DrivePath = 'M:\'
)

if (-not (Test-Path -Path $DrivePath)) {
    Write-Error "Path not found: $DrivePath"
    exit 1
}

Write-Host "Scanning files under $DrivePath ..."

$allFiles = Get-ChildItem -Path $DrivePath -File -Recurse -ErrorAction SilentlyContinue | Where-Object {
    -not ($_.FullName -match '\$RECYCLE\.BIN')
}

$allowedImageExt = @(
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.m3u'
)

$normalizedRoot = (Resolve-Path -Path $DrivePath).Path.TrimEnd('\\')

# Per-directory state across the full subtree.
$dirState = @{}

$fileCount = 0
$totalBytes = [double]0

foreach ($file in $allFiles) {
    $ext = $file.Extension.ToLowerInvariant()
    $isFlac = $ext -eq '.flac'
    $isAllowed = $isFlac -or ($allowedImageExt -contains $ext)

    if ($isFlac) {
        $fileCount++
        $totalBytes += [double]$file.Length
    }

    $dir = $file.DirectoryName
    while ($dir -and $dir.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        if (-not $dirState.ContainsKey($dir)) {
            $dirState[$dir] = [PSCustomObject]@{
                HasFlac = $false
                HasDisallowed = $false
            }
        }

        if ($isFlac) {
            $dirState[$dir].HasFlac = $true
        }

        if (-not $isAllowed) {
            $dirState[$dir].HasDisallowed = $true
        }

        if ($dir.TrimEnd('\\') -ieq $normalizedRoot) {
            break
        }

        $parent = Split-Path -Path $dir -Parent
        if ($parent -eq $dir) {
            break
        }
        $dir = $parent
    }
}

$totalMB = $totalBytes / 1MB
$totalGB = $totalBytes / 1GB

$candidateDirs = @(
    $dirState.Keys |
        Where-Object {
            $dirState[$_].HasFlac -and (-not $dirState[$_].HasDisallowed)
        } |
        Sort-Object @{ Expression = { $_.Length } }, @{ Expression = { $_ } }
)

$highestLevelDirs = New-Object System.Collections.Generic.List[string]
foreach ($candidate in $candidateDirs) {
    $isDescendant = $false
    foreach ($selected in $highestLevelDirs) {
        if ($candidate.StartsWith($selected + '\\', [System.StringComparison]::OrdinalIgnoreCase)) {
            $isDescendant = $true
            break
        }
    }

    if (-not $isDescendant) {
        [void]$highestLevelDirs.Add($candidate)
    }
}

Write-Host ""
Write-Host "FLAC file count : $fileCount"
Write-Host ("Total size      : {0:N0} bytes" -f $totalBytes)
Write-Host ("Total size      : {0:N2} MB" -f $totalMB)
Write-Host ("Total size      : {0:N2} GB" -f $totalGB)

Write-Host ""
Write-Host "Highest-level directories with only FLAC + images in their subtrees:"

if ($highestLevelDirs.Count -eq 0) {
    Write-Host "  (none found)"
}
else {
    foreach ($dir in $highestLevelDirs) {
        Write-Host ("  {0}" -f $dir)
    }
}
