# Run in PowerShell: .\test_case_generation.ps1

$BASE_DIR = Join-Path $HOME "Downloads/test_cases"

function New-SparseFile {
    param(
        [string]$Path,
        [long]$SizeBytes
    )
    $dir = Split-Path $Path -Parent
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $fs = [System.IO.File]::Create($Path)
    $fs.SetLength($SizeBytes)
    $fs.Close()
}

# ── Directory structures ──
Write-Host "`n-> Step 1: Creating directory structures..."

$dirs = @(
    "$BASE_DIR\test_case_1",
    "$BASE_DIR\test_case_2\project-alpha\docs\archive\old\v1",
    "$BASE_DIR\test_case_2\project-alpha\docs\latest",
    "$BASE_DIR\test_case_2\project-alpha\code\scripts",
    "$BASE_DIR\test_case_2\project-alpha\assets",
    "$BASE_DIR\test_case_3\small-files"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Write-Host "   Done."

# ── Test Case 1 (The Monolith — 15 GB) ──
Write-Host "-> Step 2: Allocating Test Case 1 (The Monolith - 15 GB)..."
New-SparseFile -Path "$BASE_DIR\test_case_1\large-movie.mkv" -SizeBytes (15 * 1GB)

# ── Test Case 2 (The Deep Web — 10 files per folder, 15MB to 95MB) ──
Write-Host "-> Step 3: Allocating Test Case 2 (The Deep Web)..."

# baseline files
New-SparseFile -Path "$BASE_DIR\test_case_2\project-alpha\docs\archive\old\v1\notes.txt" -SizeBytes (42 * 1KB)
New-SparseFile -Path "$BASE_DIR\test_case_2\project-alpha\docs\latest\spec.pdf"          -SizeBytes (12 * 1MB)
New-SparseFile -Path "$BASE_DIR\test_case_2\project-alpha\code\scripts\run.sh"            -SizeBytes (5 * 1KB)

# inject 10 dummy files into every folder and subfolder under test_case_2
$tc2 = "$BASE_DIR\test_case_2"
$allDirs = @($tc2) + (Get-ChildItem -Path $tc2 -Directory -Recurse | ForEach-Object { $_.FullName })

foreach ($dir in $allDirs) {
    for ($i = 1; $i -le 10; $i++) {
        $sizeMB = 15 + ($i * 8)
        New-SparseFile -Path "$dir\dummy_mb_file_$i.bin" -SizeBytes ($sizeMB * 1MB)
    }
}

# ── Test Case 3 (The Chaos Pack) ──
Write-Host "-> Step 4: Allocating Test Case 3 (The Chaos Pack)..."

New-SparseFile -Path "$BASE_DIR\test_case_3\data.bin"     -SizeBytes (21 * 1GB)
New-SparseFile -Path "$BASE_DIR\test_case_3\archive.zip"  -SizeBytes (15565 * 1MB)  # ~15.2 GB

# small explicit tracking files
New-SparseFile -Path "$BASE_DIR\test_case_3\small-files\config.json"   -SizeBytes (2 * 1KB)
New-SparseFile -Path "$BASE_DIR\test_case_3\small-files\img_001.png"   -SizeBytes (4 * 1MB)
New-SparseFile -Path "$BASE_DIR\test_case_3\small-files\img_002.png"   -SizeBytes (3994 * 1KB)  # ~3.9 MB
New-SparseFile -Path "$BASE_DIR\test_case_3\small-files\manifest.txt"  -SizeBytes (10 * 1KB)

# 105 tiny files
for ($i = 1; $i -le 105; $i++) {
    New-SparseFile -Path "$BASE_DIR\test_case_3\small-files\extra_file_$i.dat" -SizeBytes 1KB
}

# ── Verification ──
Write-Host "`n--- Verification: Structure deployed to $BASE_DIR ---`n"

Write-Host "Test Case 1:"
Get-ChildItem "$BASE_DIR\test_case_1" | Format-Table Name, @{N='Size';E={"{0:N2} GB" -f ($_.Length / 1GB)}} -AutoSize

Write-Host "Test Case 3 (first 5):"
Get-ChildItem "$BASE_DIR\test_case_3" | Select-Object -First 5 | Format-Table Name, @{N='Size';E={"{0:N2} GB" -f ($_.Length / 1GB)}} -AutoSize

Write-Host "`nDone!"
