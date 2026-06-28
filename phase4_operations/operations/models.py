"""
operations.models
-----------------
Immutable dataclasses that represent every domain concept in the
Phase 4 Railway Operations Engine.

All dataclasses are *frozen* (immutable after creation) and use
``__slots__`` for minimal memory footprint.  Complete type hints are
provided throughout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TrainType(str, Enum):
    EXPRESS = "Express"
    PASSENGER = "Passenger"
    FREIGHT = "Freight"


class ScheduleType(str, Enum):
    DAILY = "Daily"
    WEEKDAYS = "Weekdays"
    WEEKENDS = "Weekends"


class PriorityLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    EMERGENCY = "Emergency"
    FREIGHT = "Freight"


class DelayStatus(str, Enum):
    ON_TIME = "On Time"
    DELAYED = "Delayed"
    CANCELLED = "Cancelled"
    EARLY = "Early"


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Core domain dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Train:
    """A single train unit with identity and operational classification."""

    train_id: str
    train_number: str
    name: str
    train_type: TrainType
    priority: PriorityLevel
    max_speed_kmh: float
    coaches: int
    capacity: int


@dataclass(frozen=True, slots=True)
class TimetableEntry:
    """A single stop entry inside a timetable for one train."""

    entry_id: str
    train_id: str
    station_id: str
    station_name: str
    arrival_time: Optional[str]   # ISO-like "HH:MM", None for origin
    departure_time: Optional[str]  # ISO-like "HH:MM", None for terminus
    platform: int
    halt_duration_minutes: int
    stop_sequence: int


@dataclass(frozen=True, slots=True)
class TrainRoute:
    """A Phase 3 route decorated with operational metadata."""

    assignment_id: str
    train_id: str
    route_id: str
    source_id: str
    target_id: str
    station_ids: tuple[str, ...]
    station_names: tuple[str, ...]
    distance_m: float
    distance_km: float
    estimated_travel_time_minutes: float
    algorithm: str
    node_count: int
    edge_count: int


@dataclass(frozen=True, slots=True)
class OperationState:
    """Runtime operational state for a train at the moment of schedule creation."""

    state_id: str
    train_id: str
    schedule_type: ScheduleType
    is_active: bool
    current_station_id: Optional[str]
    next_station_id: Optional[str]
    delay_minutes: float
    status: DelayStatus


@dataclass(frozen=True, slots=True)
class PlatformAssignment:
    """A platform slot reservation for one train at one station."""

    assignment_id: str
    train_id: str
    station_id: str
    station_name: str
    platform_number: int
    arrival_time: Optional[str]
    departure_time: Optional[str]


@dataclass(frozen=True, slots=True)
class RouteAssignment:
    """Mapping of a train to its chosen Phase 3 route."""

    assignment_id: str
    train_id: str
    route_id: str
    distance_km: float
    estimated_travel_time_minutes: float


# ---------------------------------------------------------------------------
# Validation helpers (not frozen – built up incrementally)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ValidationIssue:
    """A single validation finding."""

    issue_id: str
    severity: ValidationSeverity
    category: str
    message: str
    affected_id: Optional[str] = None


@dataclass(slots=True)
class ValidationReport:
    """Aggregated result of all validation checks."""

    total_issues: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    passed: bool = True
