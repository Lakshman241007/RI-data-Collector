# phase2_graph — Phase 2.1: Railway Data Extraction

Extracts structured `Station` and `Track` objects from the master railway dataset produced in Phase 1 and writes validated JSON outputs ready for Phase 2.2 graph construction.

---

## Quick start

```bash
# Install dependencies (only pytest is external)
pip install -r requirements.txt

# Run the extraction pipeline
python main.py

# Run the test suite
pytest tests/ -v
```

Outputs appear in `output/`:

| File | Contents |
|---|---|
| `stations.json` | All extracted station / halt / junction / stop / platform records |
| `tracks.json` | All extracted rail / tram / subway / … track records with computed lengths |
| `statistics.json` | Aggregate counts, total track length, gauge distribution, electrification breakdown |

---

## Project structure

```
phase2_graph/
├── config/
│   └── settings.json          # All configurable paths and constants
├── graph/
│   ├── __init__.py            # Clean public API
│   ├── models.py              # Station, Track, RailwayObject dataclasses
│   ├── dataset_loader.py      # Reads master JSON → list[RailwayObject]
│   ├── station_extractor.py   # Filters station-type objects → list[Station]
│   ├── track_extractor.py     # Filters track-type objects + length → list[Track]
│   ├── exporter.py            # Writes stations.json / tracks.json
│   ├── statistics.py          # Computes and writes statistics.json
│   └── utils.py               # Shared: haversine, JSON I/O, tag helpers
├── input/
│   └── master_railway_dataset.json
├── output/                    # Created automatically
├── logs/                      # Rotating log file written here
├── tests/
│   ├── fixtures.py
│   ├── test_loader.py
│   ├── test_station_extractor.py
│   ├── test_track_extractor.py
│   └── test_exporter.py
└── main.py
```

---

## Dataset format

`master_railway_dataset.json` can be either:

- A JSON **array** of element objects: `[{…}, {…}, …]`
- An Overpass-style **dict**: `{"elements": [{…}, …]}`

Each element must have at minimum:

```json
{
  "id": "123456",
  "type": "node",
  "lat": 13.08,
  "lon": 80.27,
  "tags": { "railway": "station", "name": "Chennai Central" }
}
```

Ways provide a `"geometry"` list of `{"lat": …, "lon": …}` dicts or `[lon, lat]` pairs.

---

## Phase roadmap

| Phase | Scope |
|---|---|
| **2.1 (this)** | Data extraction — Station + Track objects |
| 2.2 | Graph construction — nodes, edges, connectivity |
| 2.3 | Routing — shortest path, journey planning |
| 2.4 | Train movement simulation |

---

## Extending for Phase 2.2

All extractors return plain dataclasses. `Station` and `Track` carry their full original `tags` dict so nothing is thrown away. Phase 2.2 can import directly:

```python
from graph import load_dataset, extract_stations, extract_tracks
```

and build graph nodes/edges from the returned lists without touching the extraction code.
