"""
Unit tests for Digital Twin process simulation and Safety Controller interlocks.
"""

import pytest
from digital_twin.actuators import ActuatorBank
from digital_twin.process_model import ProcessDigitalTwin, PhysicalProcessState
from digital_twin.rpi_gpio import HardwareInterface
from safety_controller.interlock_engine import SafetyController
from safety_controller.isolation_matrix import ActuatorIsolationMatrix, IsolationMode


def test_actuator_bank_mechanics():
    bank = ActuatorBank()
    assert len(bank.actuators) == 12  # Exceeds 10+ requirement

    # Test set target and step
    success = bank.set_target("ACT-01", 3000.0)
    assert success is True
    assert bank.actuators["ACT-01"].target_value == 3000.0

    # Advance 1.0 second
    bank.step(dt=1.0)
    # With slew_rate=600 RPM/s, value should have ramped up
    assert bank.actuators["ACT-01"].current_value > 1800.0
    assert bank.actuators["ACT-01"].current_power_w > 0.0

    # Test isolation
    bank.isolate("ACT-01")
    assert bank.actuators["ACT-01"].is_isolated is True
    assert bank.actuators["ACT-01"].current_value == bank.actuators["ACT-01"].fail_safe_value
    assert bank.actuators["ACT-01"].current_power_w == 0.0

    # Commands rejected when isolated
    assert bank.set_target("ACT-01", 2500.0) is False


def test_safety_controller_overpressure_trip():
    bank = ActuatorBank()
    matrix = ActuatorIsolationMatrix()
    hal = HardwareInterface(force_virtual=True)
    safety = SafetyController(bank, matrix, hal)
    twin = ProcessDigitalTwin(bank, hal)

    # Force dangerous overpressure (86 PSI >= 82 PSI trip threshold)
    twin.state.reactor_pressure_psi = 86.5
    trip = safety.evaluate(twin.state)

    assert trip is not None
    assert trip.severity == "CRITICAL_TRIP"
    assert "OVERPRESSURE" in trip.trigger_rule
    assert trip.reaction_time_ms < 30.0  # SIL deterministic execution

    # Verify actuator isolation
    assert matrix.is_isolated("ACT-01") is True
    assert matrix.is_isolated("ACT-06") is True
    # Emergency relief valve ACT-10 forced open
    assert bank.actuators["ACT-10"].current_value == 100.0


def test_safety_controller_thermal_runaway_trip():
    bank = ActuatorBank()
    matrix = ActuatorIsolationMatrix()
    hal = HardwareInterface(force_virtual=True)
    safety = SafetyController(bank, matrix, hal)
    twin = ProcessDigitalTwin(bank, hal)

    # Force dangerous temperature (90 °C >= 88 °C trip threshold)
    twin.state.reactor_temp_c = 90.5
    trip = safety.evaluate(twin.state)

    assert trip is not None
    assert "THERMAL" in trip.trigger_rule
    assert matrix.is_isolated("ACT-06") is True
    assert bank.actuators["ACT-07"].current_value == 100.0  # Cooling forced open


def test_safety_controller_harmonic_resonance():
    bank = ActuatorBank()
    matrix = ActuatorIsolationMatrix()
    hal = HardwareInterface(force_virtual=True)
    safety = SafetyController(bank, matrix, hal)
    twin = ProcessDigitalTwin(bank, hal)

    # Force high vibration (9.5 mm/s >= 8.0 mm/s threshold)
    twin.state.vibration_mms = 9.5
    trip = safety.evaluate(twin.state)

    assert trip is not None
    assert "RESONANCE" in trip.trigger_rule
    assert matrix.is_isolated("ACT-05") is True
    assert bank.actuators["ACT-05"].current_value == 0.0
