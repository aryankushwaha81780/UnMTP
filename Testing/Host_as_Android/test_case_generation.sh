#!/bin/bash
BASE_DIR="$HOME/storage/downloads/test_cases"

echo "➔ Step 1: Creating directory structures..."
mkdir -p "$BASE_DIR/test_case_1"
mkdir -p "$BASE_DIR/test_case_2/project-alpha/docs/archive/old/v1"
mkdir -p "$BASE_DIR/test_case_2/project-alpha/docs/latest"
mkdir -p "$BASE_DIR/test_case_2/project-alpha/code/scripts"
mkdir -p "$BASE_DIR/test_case_2/project-alpha/assets"
mkdir -p "$BASE_DIR/test_case_3/small-files"

echo "➔ Step 2: Allocating Test Case 1 (The Monolith - Modified to 15 GB)..."
truncate -s 15G "$BASE_DIR/test_case_1/large-movie.mkv"

echo "➔ Step 3: Allocating Test Case 2 (The Deep Web - Modified with 10 files per folder)..."
# Baseline files from original chart
truncate -s 42K "$BASE_DIR/test_case_2/project-alpha/docs/archive/old/v1/notes.txt"
truncate -s 12M "$BASE_DIR/test_case_2/project-alpha/docs/latest/spec.pdf"
truncate -s 5K "$BASE_DIR/test_case_2/project-alpha/code/scripts/run.sh"

# Loop through every single folder and sub-folder in test_case_2 to inject 10 files (15MB to 95MB)
find "$BASE_DIR/test_case_2" -type d | while read -r dir; do
    for i in {1..10}; do
        size=$((15 + (i * 8)))M
        truncate -s "$size" "$dir/dummy_mb_file_$i.bin"
    done
done

echo "➔ Step 4: Allocating Test Case 3 (The Chaos Pack - Unchanged)..."
truncate -s 21G "$BASE_DIR/test_case_3/data.bin"
truncate -s 15565M "$BASE_DIR/test_case_3/archive.zip" # ~15.2 GB

# Small explicit tracking files
truncate -s 2K "$BASE_DIR/test_case_3/small-files/config.json"
truncate -s 4M "$BASE_DIR/test_case_3/small-files/img_001.png"
truncate -s 3994K "$BASE_DIR/test_case_3/small-files/img_002.png" # ~3.9 MB
truncate -s 10K "$BASE_DIR/test_case_3/small-files/manifest.txt"

# Generating the remaining 100+ small files
for i in {1..105}; do
    truncate -s 1K "$BASE_DIR/test_case_3/small-files/extra_file_$i.dat"
done

echo -e "\n📊 Verification: Structure successfully deployed to $BASE_DIR\n"
ls -lh "$BASE_DIR/test_case_1"
ls -lh "$BASE_DIR/test_case_3" | head -n 5