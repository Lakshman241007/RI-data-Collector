# Phase 4.5.1 – Railway Data Collection Hub

A professional, modular **Railway Data Lake** for the RI-data-Collector project.

This phase is responsible **only** for collecting, organising, validating, archiving and documenting railway datasets.
It does **not** merge, enrich, resolve duplicates, repair topology or create master datasets — those belong to later phases.

---

## Project Structure

```
phase4_5_data_collection/
├── config/
│   ├── settings.json          # Global pipeline settings
│   ├── sources.json           # Data source URLs, licenses, dataset toggles
│   └── categories.json        # Railway category taxonomy
│
├── collectors/
│   ├── __init__.py            # BaseCollector + CollectorResult
│   ├── osm/                   # OpenStreetMap infrastructure collector
│   │   ├── __init__.py        # OSMCollector
│   │   ├── downloader.py      # Overpass API query builder & executor
│   │   ├── stations.py
│   │   ├── tracks.py
│   │   ├── platforms.py
│   │   ├── signals.py
│   │   ├── crossings.py
│   │   ├── bridges.py
│   │   ├── tunnels.py
│   │   └── electrification.py
│   ├── official/              # Indian Railways official metadata collector
│   │   ├── __init__.py        # OfficialCollector
│   │   ├── downloader.py      # data.gov.in paginated API client
│   │   ├── station_master.py
│   │   ├── station_codes.py
│   │   ├── railway_zones.py
│   │   ├── railway_divisions.py
│   │   └── train_master.py
│   ├── public/                # Public open-data collector
│   │   ├── __init__.py        # PublicCollector
│   │   ├── downloader.py      # Generic JSON URL fetcher
│   │   ├── trains.py
│   │   ├── timetables.py
│   │   ├── facilities.py
│   │   └── elevations.py
│   └── metadata/              # Descriptive metadata collector
│       ├── __init__.py        # MetadataCollector
│       ├── downloader.py      # Wikipedia API client
│       ├── aliases.py
│       ├── wikipedia.py
│       ├── station_history.py
│       └── amenities.py
│
├── common/                    # Shared utilities (no duplication)
│   ├── __init__.py
│   ├── checksum.py            # SHA-256 file integrity
│   ├── downloader.py          # HTTP downloader with retry
│   ├── file_utils.py          # FS helpers, archiving, timestamps
│   ├── json_utils.py          # JSON read/write
│   ├── logger.py              # Logging factory
│   ├── manifest.py            # Manifest generation & serialisation
│   └── validator.py           # File & record validation
│
├── raw/                       # Permanent raw archives (never modified)
│   ├── osm/
│   ├── official/
│   ├── public/
│   └── metadata/
│
├── processed/                 # Cleaned copies (no merge / enrichment)
│   ├── osm/
│   ├── official/
│   ├── public/
│   └── metadata/
│
├── manifests/                 # Per-collector manifests (JSON)
│   ├── osm_manifest.json
│   ├── official_manifest.json
│   ├── public_manifest.json
│   └── metadata_manifest.json
│
├── logs/                      # Separate log file per collector
│   ├── osm.log
│   ├── official.log
│   ├── public.log
│   ├── metadata.log
│   └── pipeline.log
│
├── reference/                 # Static reference data (not collected)
├── tests/                     # Unit & integration tests
│   ├── conftest.py
│   ├── test_common.py
│   ├── test_manifest.py
│   ├── test_collectors.py
│   ├── test_validation.py
│   └── test_pipeline.py
│
├── main.py                    # Pipeline entry point
├── pytest.ini
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the full pipeline

```bash
python main.py
```

### 3. Dry-run (no network calls)

```bash
python main.py --dry-run
```

### 4. Custom config path

```bash
python main.py --config /path/to/settings.json
```

### 5. Run tests

```bash
pytest
# or with coverage:
pytest --cov=. --cov-report=term-missing
```

---

## Collectors

| Collector   | Source                         | Datasets          | Raw Dir           |
|-------------|--------------------------------|-------------------|-------------------|
| `osm`       | OpenStreetMap / Overpass API   | 8 infrastructure  | `raw/osm/`        |
| `official`  | data.gov.in / Indian Railways  | 5 official meta   | `raw/official/`   |
| `public`    | datameet/railways (GitHub)     | 4 public datasets | `raw/public/`     |
| `metadata`  | Wikipedia API + curated seeds  | 4 descriptor sets | `raw/metadata/`   |

### OSM Collector

Queries the [Overpass API](https://overpass-api.de) for Indian railway infrastructure:

- **stations** – `railway=station` nodes  
- **tracks** – `railway=rail` ways  
- **platforms** – `railway=platform`  
- **signals** – `railway=signal` nodes  
- **crossings** – `railway=crossing` nodes  
- **bridges** – `bridge=yes` elements on rail ways  
- **tunnels** – `tunnel=yes` elements on rail ways  
- **electrification** – `electrified=*` elements  

### Official Collector

Downloads paginated JSON from data.gov.in:

- `station_master` – full station listing with coordinates  
- `station_codes` – IRCTC station code mappings  
- `railway_zones` – the 18 IR administrative zones  
- `railway_divisions` – all railway divisions per zone  
- `train_master` – complete train catalogue  

### Public Collector

Fetches JSON datasets from public repositories:

- `trains` – train list with route info  
- `timetables` – schedule/stop data  
- `facilities` – station amenity flags  
- `elevations` – station elevation GeoJSON  

### Metadata Collector

Collects descriptive metadata:

- `aliases` – alternate/regional station names (curated seed, expandable)  
- `wikipedia` – article extracts for major stations via Wikipedia API  
- `station_history` – opening year, original zone, historical notes  
- `amenities` – structured amenity list per station  

---

## Configuration

### `config/settings.json`

Controls global pipeline behaviour:

```json
{
  "cache_enabled": true,
  "overwrite_existing": false,
  "collectors": {
    "osm": { "enabled": true, "timeout_seconds": 120, "retries": 3 }
  }
}
```

Set `"enabled": false` for any collector or dataset to skip it.  
Set `"overwrite_existing": true` to force re-download ignoring cache.

### `config/sources.json`

Defines every data source, URL, license and per-dataset toggles.

### `config/categories.json`

Defines the railway category taxonomy used across phases.

---

## Architecture Principles

- **Every collector is independent.** No collector imports from another.  
- **Communication only through `common/` and `config/`.** No shared global state.  
- **Raw data is never modified.** Files in `raw/` are permanent archives.  
- **Single responsibility.** Each module has one job.  
- **No duplicated code.** All utilities live in `common/`.  
- **Graceful error handling.** Failures are logged and captured in `CollectorResult`; the pipeline continues.  
- **Caching.** Files already downloaded are not re-fetched unless `overwrite_existing: true`.

---

## Manifests

Each collector writes a manifest to `manifests/<name>_manifest.json` containing:

- `source_name`, `license`, `dataset_version`  
- `download_timestamp`  
- Per-dataset entries: `checksum_sha256`, `file_size_bytes`, `record_count`, `validation_passed`  
- `validation_summary`: counts of passed / failed / warnings  
- `total_records`, `total_size_bytes`  

---

## Outputs

After a successful run:

```
raw/osm/         stations.json, tracks.json, platforms.json, …
raw/official/    station_master.json, station_codes.json, …
raw/public/      trains.json, timetables.json, facilities.json, elevations.json
raw/metadata/    aliases.json, wikipedia.json, station_history.json, amenities.json

manifests/       osm_manifest.json, official_manifest.json, …
logs/            osm.log, official.log, public.log, metadata.log, pipeline.log
statistics.json  Pipeline-level run statistics
```

---

## Phase Boundary

This phase (**4.5.1**) outputs independent, validated raw datasets.

**It does NOT:**
- Merge datasets  
- Enrich metadata  
- Resolve duplicates  
- Repair topology  
- Create a master station list  

Those operations belong to **Phase 4.5.2** (Data Harmonisation & Enrichment).

---

## License

Project code: MIT.  
Dataset licenses are tracked per-collector in manifests and `sources.json`.


Collector
    ↓
official_sources.json
    ↓
data_registry/datasets/
    ↓
data_registry/providers/
    ↓
data_registry/mappings/
    ↓
data_registry/policies/
    ↓
Downloader