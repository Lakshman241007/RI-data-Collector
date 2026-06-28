# Railway Data Collection Platform — Phase 1

Phase 1 builds a robust railway infrastructure collection pipeline for
**Tamil Nadu**, combining two data sources into one validated master
dataset:

1. **OpenStreetMap Overpass API** — latest railway edits, small
   updates, validation.
2. **GeoFabrik India Extract** (`india-latest.osm.pbf`) — complete
   offline bulk railway dataset.

> This phase only collects, merges, and validates raw railway
> infrastructure data. Station classification, route building, gradient
> calculation, network graphs, delay modelling, and simulation are out
> of scope and belong to later phases.

## Project layout

```
phase1_osm/
├── config/
│   └── settings.json        # all configurable values live here
├── extractor/
│   ├── config.py             # typed settings.json loader
│   ├── models.py              # shared RailwayObject data model
│   ├── overpass.py            # Overpass API client + raw parser
│   ├── geofabrik.py           # GeoFabrik PBF downloader
│   ├── pbf_reader.py          # pyosmium-based PBF railway extractor
│   ├── merger.py               # GeoFabrik + Overpass merge engine
│   ├── validator.py            # dataset quality validation
│   └── logging_utils.py        # per-component log file setup
├── input/                     # downloaded india-latest.osm.pbf lands here
├── logs/                      # pipeline.log, overpass.log, geofabrik.log
├── output/                    # all generated JSON outputs
├── tests/                     # unit tests for every module
├── main.py                    # pipeline entry point
└── requirements.txt
```

## Setup

```bash
cd phase1_osm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the pipeline

```bash
python main.py
```

This will, without manual intervention:

1. Load `config/settings.json`.
2. Health-check the Overpass endpoint.
3. Download `india-latest.osm.pbf` into `input/` if it isn't already
   present (resuming a partial download if one exists).
4. Read the PBF with `pyosmium`, keeping only `railway=*` nodes, ways,
   and relations.
5. Fetch the latest `railway=*` edits for Tamil Nadu from Overpass.
6. Merge both datasets — Overpass wins on duplicate OSM ids, since it
   reflects the most recent edits; every railway tag is preserved.
7. Validate the merged dataset (missing ids/coordinates, duplicate
   ids, unrecognised railway tag values, broken geometry).
8. Write all outputs to `output/`.

### Outputs

| File | Description |
|---|---|
| `output/raw_overpass.json` | Raw Overpass API response |
| `output/raw_geofabrik.json` | Structured railway objects extracted from the PBF |
| `output/master_railway_dataset.json` | Final merged + deduplicated dataset |
| `output/validation.json` | Validation report and issue list |
| `output/statistics.json` | Run statistics (counts, duplicates, timing) |

### Logs

| File | Contents |
|---|---|
| `logs/overpass.log` | Overpass client activity only |
| `logs/geofabrik.log` | GeoFabrik download + PBF read activity only |
| `logs/pipeline.log` | Full combined pipeline log |

## Configuration

Everything is controlled from `config/settings.json`:

```json
{
  "overpass": {
    "endpoint": "https://overpass-api.de/api/interpreter",
    "timeout": 90,
    "retries": 3,
    "retry_backoff": 5,
    "region": "Tamil Nadu"
  },
  "geofabrik": {
    "url": "https://download.geofabrik.de/asia/india-latest.osm.pbf",
    "download_dir": "input",
    "filename": "india-latest.osm.pbf",
    "chunk_size": 8192
  },
  "output": { "...": "..." },
  "logging": { "log_dir": "logs", "level": "INFO" }
}
```

## Tests

```bash
pytest
```

Covers the Overpass client (health check, retry, parsing), the
GeoFabrik downloader (fresh download, resume, skip-existing), the PBF
reader (against a small synthetic `.osm` fixture), the merge engine,
and the validator.

## Data model

Every railway feature — regardless of source — is normalized into a
`RailwayObject`:

```python
RailwayObject(
    osm_id=123456,
    osm_type="way",       # "node" | "way" | "relation"
    tags={"railway": "rail", "gauge": "1676"},
    geometry=[[80.27, 13.08], [80.28, 13.09]],
    source="overpass",    # "overpass" | "geofabrik"
    version=4,
    timestamp="2026-05-01T10:00:00Z",
)
```
