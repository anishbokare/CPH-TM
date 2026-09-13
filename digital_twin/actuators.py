"""
Actuator Subsystem Models for the Cyber-Physical Digital Twin.
Defines 12 industrial actuators (exceeding the 10+ actuator requirement)
with realistic electromechanical inertia, energy draw, and wear-and-tear models.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List


@dataclass
class ActuatorState:
    actuator_id: str
    name: str
    category: str           # 'pump', 'valve', 'heater', 'agitator', 'damper'
    unit: str               # 'RPM', '%', 'kW', 'deg'
    min_value: float
    max_value: float
    target_value: float
    current_value: float
    slew_rate: float        # Max units per second (inertia)
    power_rating_w: float   # Max power in Watts
    current_power_w: float = 0.0
    is_isolated: bool = False
    fail_safe_value: float = 0.0
    wear_index: float = 0.0 # 0.0 to 1.0 (cumulative physical stress)
    last_update: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ActuatorBank:
    """Controls and updates the bank of 12 industrial actuators."""

    def __init__(self):
        self.actuators: Dict[str, ActuatorState] = {
            "ACT-01": ActuatorState(
                actuator_id="ACT-01",
                name="Primary Feed Pump",
                category="pump",
                unit="RPM",
                min_value=0.0,
                max_value=3600.0,
                target_value=1800.0,
                current_value=1800.0,
                slew_rate=600.0,
                power_rating_w=4500.0,
                fail_safe_value=0.0,
            ),
            "ACT-02": ActuatorState(
                actuator_id="ACT-02",
                name="Inflow Proportional Valve",
                category="valve",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=50.0,
                current_value=50.0,
                slew_rate=25.0,
                power_rating_w=120.0,
                fail_safe_value=0.0,
            ),
            "ACT-03": ActuatorState(
                actuator_id="ACT-03",
                name="Acid Dosing Peristaltic Pump",
                category="pump",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=20.0,
                current_value=20.0,
                slew_rate=30.0,
                power_rating_w=250.0,
                fail_safe_value=0.0,
            ),
            "ACT-04": ActuatorState(
                actuator_id="ACT-04",
                name="Base Neutralizer Pump",
                category="pump",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=20.0,
                current_value=20.0,
                slew_rate=30.0,
                power_rating_w=250.0,
                fail_safe_value=0.0,
            ),
            "ACT-05": ActuatorState(
                actuator_id="ACT-05",
                name="Reactor Impeller / Agitator",
                category="agitator",
                unit="RPM",
                min_value=0.0,
                max_value=1800.0,
                target_value=1200.0,
                current_value=1200.0,
                slew_rate=400.0,
                power_rating_w=2200.0,
                fail_safe_value=0.0,
            ),
            "ACT-06": ActuatorState(
                actuator_id="ACT-06",
                name="Primary Heating Grid",
                category="heater",
                unit="kW",
                min_value=0.0,
                max_value=15.0,
                target_value=5.0,
                current_value=5.0,
                slew_rate=3.0,
                power_rating_w=15000.0,
                fail_safe_value=0.0,
            ),
            "ACT-07": ActuatorState(
                actuator_id="ACT-07",
                name="Cooling Jacket Valve",
                category="valve",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=35.0,
                current_value=35.0,
                slew_rate=40.0,
                power_rating_w=150.0,
                fail_safe_value=100.0,  # Fail open to dissipate heat
            ),
            "ACT-08": ActuatorState(
                actuator_id="ACT-08",
                name="Secondary Transfer Pump",
                category="pump",
                unit="RPM",
                min_value=0.0,
                max_value=3000.0,
                target_value=1500.0,
                current_value=1500.0,
                slew_rate=500.0,
                power_rating_w=3500.0,
                fail_safe_value=0.0,
            ),
            "ACT-09": ActuatorState(
                actuator_id="ACT-09",
                name="Filter Backwash Valve",
                category="valve",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=0.0,
                current_value=0.0,
                slew_rate=100.0,  # High speed solenoid
                power_rating_w=80.0,
                fail_safe_value=0.0,
            ),
            "ACT-10": ActuatorState(
                actuator_id="ACT-10",
                name="Emergency Pressure Relief Valve",
                category="valve",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=0.0,
                current_value=0.0,
                slew_rate=200.0,  # Instantaneous pneumatic dump
                power_rating_w=200.0,
                fail_safe_value=100.0,  # Fail open to prevent rupture
            ),
            "ACT-11": ActuatorState(
                actuator_id="ACT-11",
                name="Sludge Bottom Drain Valve",
                category="valve",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                target_value=0.0,
                current_value=0.0,
                slew_rate=50.0,
                power_rating_w=110.0,
                fail_safe_value=0.0,
            ),
            "ACT-12": ActuatorState(
                actuator_id="ACT-12",
                name="Exhaust Scrubber Damper",
                category="damper",
                unit="deg",
                min_value=0.0,
                max_value=90.0,
                target_value=45.0,
                current_value=45.0,
                slew_rate=30.0,
                power_rating_w=90.0,
                fail_safe_value=90.0,  # Fail open to vent hazardous vapor
            ),
        }

    def set_target(self, actuator_id: str, value: float) -> bool:
        """Set commanded setpoint for an actuator (if not isolated)."""
        act = self.actuators.get(actuator_id)
        if not act:
            return False
        if act.is_isolated:
            return False  # Blocked by safety controller isolation relay

        clamped = max(act.min_value, min(act.max_value, float(value)))
        act.target_value = clamped
        return True

    def isolate(self, actuator_id: str) -> None:
        """Trip isolation relay and drive actuator to deterministic fail-safe clamp."""
        act = self.actuators.get(actuator_id)
        if act:
            act.is_isolated = True
            act.target_value = act.fail_safe_value
            act.current_value = act.fail_safe_value  # Instant mechanical spring / relay trip
            act.current_power_w = 0.0

    def restore(self, actuator_id: str) -> None:
        """Clear isolation state."""
        act = self.actuators.get(actuator_id)
        if act:
            act.is_isolated = False

    def isolate_all(self) -> None:
        """E-Stop / Full plant actuator isolation."""
        for act_id in self.actuators:
            self.isolate(act_id)

    def restore_all(self) -> None:
        for act in self.actuators.values():
            act.is_isolated = False
            # Restore standard baseline operating target
            if act.category == "pump":
                act.target_value = (act.max_value - act.min_value) * 0.4
            elif act.category == "heater":
                act.target_value = 4.0
            elif act.actuator_id in ("ACT-07", "ACT-12"):
                act.target_value = 40.0
            else:
                act.target_value = 0.0

    def step(self, dt: float) -> None:
        """Advance actuator electromechanical physics by dt seconds."""
        now = time.time()
        for act in self.actuators.values():
            if act.is_isolated:
                act.current_value = act.fail_safe_value
                act.current_power_w = 0.0
                act.last_update = now
                continue

            # Ramp current towards target based on slew rate
            diff = act.target_value - act.current_value
            max_step = act.slew_rate * dt
            if abs(diff) <= max_step:
                act.current_value = act.target_value
            else:
                act.current_value += max_step if diff > 0 else -max_step

            # Calculate proportional electrical load
            fraction = (act.current_value - act.min_value) / max(1.0, (act.max_value - act.min_value))
            act.current_power_w = round(fraction * act.power_rating_w, 1)

            # Wear accumulation if driven at high load
            if fraction > 0.85:
                act.wear_index = min(1.0, act.wear_index + 0.0002 * dt)

            act.last_update = now

    def get_states(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.to_dict() for k, v in self.actuators.items()}
