"""
Unit tests for Forensic Correlation and MITRE ATT&CK for ICS mapping.
"""

import time
from honeynet.packet_logger import PacketLogger
from digital_twin.process_model import PhysicalProcessState
from safety_controller.interlock_engine import SafetyTripEvent
from forensics.correlator import ForensicCorrelator
from forensics.mitre_ics import classify_attack
from forensics.reconstruction import AttackReconstructionEngine


def test_mitre_classification():
    # Test unauthorized command
    tech1 = classify_attack(protocol="MODBUS_TCP", function_code=5, target_actuator="ACT-01", physical_deviation_type=None)
    assert tech1["id"] == "T0855"

    # Test parameter modification
    tech2 = classify_attack(protocol="MODBUS_TCP", function_code=6, target_actuator="ACT-06", physical_deviation_type=None)
    assert tech2["id"] == "T0836"

    # Test physical impact (damage to property)
    tech3 = classify_attack(protocol="MODBUS_TCP", function_code=6, target_actuator="ACT-01", physical_deviation_type="OVERPRESSURE")
    assert tech3["id"] == "T0879"


def test_forensic_correlator_timeline():
    logger = PacketLogger()
    correlator = ForensicCorrelator()
    logger.add_listener(correlator.on_network_event)

    # 1. Attacker sends Modbus write
    net_evt = logger.create_and_log(
        protocol="MODBUS_TCP",
        source_ip="192.168.1.200",
        source_port=45000,
        dest_ip="127.0.0.1",
        dest_port=1502,
        function_code=6,
        address=0,
        value=980,
        is_anomaly=True,
        anomaly_reason="Dangerous overpressure injection",
    )

    # 2. Safety Controller trips
    trip = SafetyTripEvent(
        trip_id="TRIP-00001",
        timestamp=time.time() + 0.05,
        trigger_rule="OVERPRESSURE_CRITICAL_INTERLOCK",
        severity="CRITICAL_TRIP",
        measured_value=87.2,
        threshold_value=82.0,
        unit="PSI",
        affected_actuators=["ACT-01", "ACT-02", "ACT-06", "ACT-10"],
        action_taken="De-energized feed pumps and opened relief valve",
        damage_prevented="Vessel rupture",
        reaction_time_ms=11.2,
    )

    state = PhysicalProcessState(
        timestamp=time.time(),
        reactor_pressure_psi=87.2,
        reactor_temp_c=65.0,
    )

    incident = correlator.on_safety_trip(trip, state)

    assert incident is not None
    assert incident.protocol == "MODBUS_TCP"
    assert incident.source_ip == "192.168.1.200"
    assert incident.safety_intervened is True
    assert incident.mitre_technique_id == "T0879"
    assert incident.reaction_time_ms == 11.2


def test_reconstruction_engine_accuracy():
    engine = AttackReconstructionEngine()

    scenario = {
        "scenario_id": "SCN-0001",
        "mitre_id": "T0879",
        "target_actuator": "ACT-01",
        "impact_type": "OVERPRESSURE",
    }

    # Simulate incident matching ground truth
    from forensics.correlator import CorrelatedIncident
    incident = CorrelatedIncident(
        incident_id="INC-00001",
        timestamp=time.time(),
        network_event_id="NET-000001",
        protocol="MODBUS_TCP",
        source_ip="192.168.1.105",
        command_type="Write Single Register",
        payload_summary="Pressure setpoint 950 PSI",
        physical_impact_type="OVERPRESSURE",
        deviation_description="Pressure surge",
        peak_pressure_psi=86.0,
        peak_temp_c=64.0,
        peak_vibration_mms=1.2,
        targeted_actuators=["ACT-01"],
        safety_intervened=True,
        mitre_technique_id="T0879",
    )

    res = engine.evaluate_incident(incident, scenario)
    assert res.is_overall_success is True
    assert res.confidence_score >= 0.9

    metrics = engine.get_aggregate_metrics()
    assert metrics["accuracy_pct"] == 100.0
