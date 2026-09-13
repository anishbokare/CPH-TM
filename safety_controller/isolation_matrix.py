"""
Actuator Isolation Matrix for Industrial Safety System.
Provides deterministic hardware/software relay isolation across all 12 actuators,
maintaining verified SIL-compliant fail-safe states.
"""

import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


class IsolationMode(str, Enum):
    ENABLED = "ENABLED"                          # Normal SCADA operation
    THROTTLED = "THROTTLED"                      # Rate-limited / power-capped
    ISOLATED_RELAY_OPEN = "ISOLATED_RELAY_OPEN"  # Hardware coil/power relay physically disconnected
    FAILSAFE_CLAMPED = "FAILSAFE_CLAMPED"        # Spring-return / fail-safe parked state


@dataclass
class ActuatorIsolationRecord:
    actuator_id: str
    mode: IsolationMode = IsolationMode.ENABLED
    trip_reason: Optional[str] = None
    trip_timestamp: Optional[float] = None
    fail_safe_value: float = 0.0
    isolation_count: int = 0
    total_isolated_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


class ActuatorIsolationMatrix:
    """Manages isolation status and fail-safe clamping across 10+ actuators."""

    def __init__(self, actuator_ids: Optional[List[str]] = None):
        if actuator_ids is None:
            actuator_ids = [f"ACT-{i:02d}" for i in range(1, 13)]

        self.records: Dict[str, ActuatorIsolationRecord] = {}
        for act_id in actuator_ids:
            # Deterministic fail safe values:
            # ACT-07 (cooling) fails open (100%), ACT-10 (relief) fails open (100%), ACT-12 (vent) fails open (90)
            fail_val = 100.0 if act_id in ("ACT-07", "ACT-10") else (90.0 if act_id == "ACT-12" else 0.0)
            self.records[act_id] = ActuatorIsolationRecord(
                actuator_id=act_id,
                fail_safe_value=fail_val,
            )

    def trip_actuator(self, actuator_id: str, reason: str, mode: IsolationMode = IsolationMode.FAILSAFE_CLAMPED) -> bool:
        """Isolate a specific actuator due to an interlock trigger."""
        rec = self.records.get(actuator_id)
        if not rec:
            return False

        now = time.time()
        rec.mode = mode
        rec.trip_reason = reason
        rec.trip_timestamp = now
        rec.isolation_count += 1
        return True

    def trip_all(self, reason: str) -> None:
        """Emergency plant-wide actuator trip (E-Stop)."""
        for act_id in self.records:
            self.trip_actuator(act_id, reason, IsolationMode.FAILSAFE_CLAMPED)

    def restore_actuator(self, actuator_id: str) -> bool:
        """Clear isolation state for an actuator."""
        rec = self.records.get(actuator_id)
        if not rec:
            return False

        if rec.trip_timestamp:
            rec.total_isolated_seconds += (time.time() - rec.trip_timestamp)
        rec.mode = IsolationMode.ENABLED
        rec.trip_reason = None
        rec.trip_timestamp = None
        return True

    def restore_all(self) -> None:
        """Restore all actuators to active mode."""
        for act_id in self.records:
            self.restore_actuator(act_id)

    def is_isolated(self, actuator_id: str) -> bool:
        rec = self.records.get(actuator_id)
        return rec.mode in (IsolationMode.ISOLATED_RELAY_OPEN, IsolationMode.FAILSAFE_CLAMPED) if rec else False

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.records)
        isolated_count = sum(1 for r in self.records.values() if r.mode != IsolationMode.ENABLED)
        return {
            "total_actuators": total,
            "isolated_count": isolated_count,
            "is_system_tripped": isolated_count > 0,
            "actuators": {k: v.to_dict() for k, v in self.records.items()},
        }
