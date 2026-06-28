# Phase 4 – Railway Operations Engine

> Tamil Nadu Railway Simulation · Phase 4 of N

## Overview

Phase 4 consumes the **Phase 3** route graph and route catalogue to produce a
fully initialised operational dataset ready for a physics / animation engine.

This phase is **not** responsible for physics or animation.  
It creates train objects, schedules, timetables, and operational state.

---

## Project structure

```
phase4_operations/
├── config/
│   └── operations_settings.json   # Tuneable parameters
├── input/
│   ├── railway_graph.json          # Phase 3 graph (read-only)
│   └── routes.json                 # Phase 3 routes (read-only)
├── operations/
│   ├── __init__.py
│   ├── models.py                   # Immutable dataclasses
│   ├── train_loader.py             # Train generation & validation
│   ├── timetable_loader.py         # Timetable construction
│   ├── route_assigner.py           # Phase 3 route assignment
│   ├── scheduler.py                # Schedule type assignment
│   ├── priority_manager.py         # Priority ordering & indexing
│   ├── delay_manager.py            # Delay & expected-time computation
│   ├── platform_manager.py         # Platform assignment & conflict detection
│   ├── operations_validator.py     # Full operational validation
│   ├── statistics.py               # Aggregated statistics
│   └── exporter.py                 # JSON output writer
├── output/                         # Generated at runtime
│   ├── trains.json
│   ├── timetables.json
│   ├── operations.json
│   ├── statistics.json
│   └── validation.json
├── logs/
│   └── phase4_operations.log
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_train_loader.py
│   ├── test_timetable_loader.py
│   ├── test_route_assigner.py
│   ├── test_scheduler.py
│   ├── test_priority_manager.py
│   ├── test_delay_manager.py
│   ├── test_platform_manager.py
│   ├── test_operations_validator.py
│   ├── test_statistics.py
│   └── test_exporter.py
├── main.py
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Requirements

* **Python 3.13** (stdlib only; no third-party runtime dependencies)
* `pytest ≥ 8.0` and `pytest-cov ≥ 5.0` for tests

---

## Quick start

```bash
# 1 – Install test dependencies
pip install -r requirements.txt

# 2 – Run the engine
python main.py

# 3 – Run the test suite
pytest
```

---

## Configuration (`config/operations_settings.json`)

| Key | Default | Description |
|-----|---------|-------------|
| `train_count` | 50 | Number of trains to generate |
| `speed_kmh` | Express 110 / Passenger 70 / Freight 45 | Max speed per type |
| `halt_duration_minutes` | Express 5 / Passenger 10 / Freight 15 | Halt time at intermediate stops |
| `platform_count` | 6 | Platforms per station |
| `base_departure_hour` | 5 | Hour at which train 1 departs |
| `schedule_gap_minutes` | 20 | Departure gap between successive trains |

---

## Modules

| Module | Responsibility |
|--------|---------------|
| `models.py` | Frozen dataclasses – `Train`, `TimetableEntry`, `TrainRoute`, `OperationState`, `PlatformAssignment`, `RouteAssignment` |
| `train_loader.py` | Generate trains, assign IDs/numbers, validate uniqueness |
| `timetable_loader.py` | Compute arrival / departure times, platforms, halt durations |
| `route_assigner.py` | Map each train to a Phase 3 route; compute distance & travel time |
| `scheduler.py` | Assign Daily / Weekdays / Weekends schedule type per train |
| `priority_manager.py` | Build priority index; sort trains by operational priority |
| `delay_manager.py` | Compute delay status and expected times; build `OperationState` |
| `platform_manager.py` | Assign platforms; detect time-overlap conflicts |
| `operations_validator.py` | Aggregate all validation checks into a `ValidationReport` |
| `statistics.py` | Compute summary metrics from the complete dataset |
| `exporter.py` | Write all five JSON artefacts to `output/` |

---

## Output files

| File | Contents |
|------|----------|
| `trains.json` | Full train catalogue (type, priority, speed, coaches, capacity) |
| `timetables.json` | All stop entries (arrival, departure, platform, halt duration) |
| `operations.json` | Route assignments · operation states · platform assignments · schedules |
| `statistics.json` | Aggregate metrics (counts, travel times, platform utilisation, …) |
| `validation.json` | Validation report (passed flag, error/warning counts, issue list) |

---

## Design principles

* **Immutability** – every domain object is a `frozen=True` dataclass.
* **Single responsibility** – one module, one concern.
* **No global mutable state** – all data flows through function parameters and return values.
* **No duplication** – shared helpers live in `models.py`; no copy-paste logic.
* **Phase isolation** – Phase 3 files are read but never modified.
