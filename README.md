# syno-photo-tidy

A Windows photo organizer that **never deletes files**. It isolates recovered thumbnails, deduplicates photos (exact hash + perceptual hash), keeps only the highest-resolution version per duplicate group, and moves everything else into a `TO_DELETE` folder. Optional features include Synology Photos–style renaming and year/month archiving. Every run generates a `manifest.json` to support full rollback (undo).

## Key Features
- **Folder picker GUI (Windows)**
- **Dry-run preview** (no file changes) with summary statistics
- **Thumbnail isolation** (small file + low resolution rules)
- **Deduplication**
  - Exact duplicates via file hash (MD5/SHA)
  - Near-duplicates via perceptual hash (pHash)
- **Keep only the best version**
  - Prefer highest resolution (`width * height`)
  - Tie-breakers: larger file size, richer EXIF metadata
- **Safe operations**
  - **Move only, no delete**
  - `manifest.json` generated every run for rollback (undo)
- **Synology-style renaming (optional)**
  - `IMG_yyyyMMdd_HHmmss(_###).ext`
  - Timestamp source order: EXIF → file creation time → original name + sequence
- **Archiving (optional)**
  - Move kept photos into `YYYY/` or `YYYY-MM/` subfolders

## Safety Guarantees (Non-negotiables)
- The tool **never deletes** files.
- All removals are implemented as **moves** into `TO_DELETE/`.
- Every operation writes a `REPORT/manifest.json` for rollback.
- A **dry-run** is available before any file operations.

## Output Folder Structure
After running, the tool creates an output root folder (example: `Processed_20260210_093000/`):

- `KEEP/`  
  - (optional) `YYYY/` or `YYYY-MM/` subfolders
- `TO_DELETE/`
  - `THUMBNAILS/`
  - `DUPLICATES_EXACT/`
  - `DUPLICATES_SIMILAR/`
- `REPORT/`
  - `manifest.json`
  - `report.csv`
  - `summary.txt`
  - `error.log`

## How It Works (Pipeline)
1. Scan folder and collect metadata (size, resolution, EXIF timestamp if available)
2. Isolate thumbnails → move candidates to `TO_DELETE/THUMBNAILS/`
3. Exact dedupe (hash) → keep one, move the rest to `TO_DELETE/DUPLICATES_EXACT/`
4. Near-dedupe (pHash) → cluster similar images, keep best resolution, move the rest to `TO_DELETE/DUPLICATES_SIMILAR/`
5. Optional rename (Synology format) on **kept** files
6. Optional archive into year/month subfolders
7. Generate reports + manifest for rollback

## Configuration
The tool reads a config file (planned): `config.json`

Example fields (planned):
- Thumbnail rules:
  - `max_file_kb`
  - `max_long_edge_px`
- pHash:
  - `phash_distance_threshold`
- Rename:
  - `enable_rename`
  - `collision_suffix_digits`
- Archive:
  - `enable_archive`
  - `mode`: `year` or `month`
- Time source:
  - `timestamp_priority`: `exif` → `created_time` → `fallback`

## Rollback (Undo)
- Use `REPORT/manifest.json` from the last run to move files back to their original paths.
- If a destination path is occupied, the tool should place files into a safe fallback folder and report conflicts in `error.log`.

## Roadmap
- v0.1: Tkinter GUI + dry-run scan + thumbnail isolation
- v0.2: Exact dedupe (hash) + reporting
- v0.3: pHash clustering + keep-best-resolution policy
- v0.4: Move executor + manifest rollback
- v0.5: Synology renaming + year/month archiving
- v1.0: Packaging (Windows executable) + improved UI

## License
Choose a license (MIT recommended for personal utilities).

## GUI Options
- ✅ Dry-run preview (default ON for preview step)
- ✅ Enable renaming (default OFF)
  - When enabled, renaming applies **only** to files moved into `KEEP/`
  - Format: `IMG_yyyyMMdd_HHmmss(_###).ext`
- ✅ Enable archiving (default OFF)
  - Archive mode: `year` or `month`
