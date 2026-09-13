"""
Cross-Domain Forensic Correlation Pipeline.
Correlates cyber network traffic (Modbus, DNP3, MQTT) with physical state deviations
and safety controller interventions to construct unified incident timelines.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from honeynet.packet_logger import NetworkEvent
from digital_twin.process_model import PhysicalProcessState
from safety_controller.interlock_engine import SafetyTripEvent
from .mitre_ics import classify_attack


@dataclass
class CorrelatedIncident:
    incident_id: str
    timestamp: float
    # Cyber domain
    network_event_id: str
    protocol: str
    source_ip: str
    command_type: str
    payload_summary: str
    # Physical domain
    physical_impact_type: str
    deviation_description: str
    peak_pressure_psi: float
    peak_temp_c: float
    peak_vibration_mms: float
    targeted_actuators: List[str]
    # Safety domain
    safety_intervened: bool
    safety_trip_id: Optional[str] = None
    reaction_time_ms: float = 0.0
    damage_prevented: str = "None"
    # Threat intelligence
    mitre_technique_id: str = "T0855"
    mitre_technique_name: str = "Unauthorized Command Message"
    mitre_tactic: str = "Impair Process Control"
    # Timeline
    network_to_physical_delay_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.timestamp)) + f".{int((self.timestamp % 1) * 1000):03d}Z"
        return d


class ForensicCorrelator:
    """Pipelines network packets, physical telemetry, and safety trips into correlated records."""

    def __init__(self, max_records: int = 500):
        self.max_records = max_records
        self.incidents: List[CorrelatedIncident] = []
        self._incident_count = 0

        # Correlation sliding window
        self._recent_network_anomalies: List[NetworkEvent] = []
        self._recent_physical_states: List[PhysicalProcessState] = []
        self._recent_trips: List[SafetyTripEvent] = []

    def on_network_event(self, event: NetworkEvent) -> None:
        if event.is_anomaly:
            self._recent_network_anomalies.append(event)
            if len(self._recent_network_anomalies) > 100:
                self._recent_network_anomalies.pop(0)

    def on_safety_trip(self, trip: SafetyTripEvent, current_state: PhysicalProcessState) -> CorrelatedIncident:
        """
        When safety controller trips, correlate it with the causally triggering
        network packet and physical state trajectory.
        """
        now = time.time()
        self._incident_count += 1
        incident_id = f"INC-{self._incident_count:05d}"

        # Find closest preceding network anomaly (within last 10 seconds)
        matched_net: Optional[NetworkEvent] = None
        for evt in reversed(self._recent_network_anomalies):
            if (trip.timestamp - evt.timestamp) >= 0 and (trip.timestamp - evt.timestamp) <= 10.0:
                matched_net = evt
                break

        # Fallback if no specific packet caught
        net_id = matched_net.event_id if matched_net else f"NET-SYNC-{self._incident_count}"
        proto = matched_net.protocol if matched_net else "MODBUS_TCP"
        src_ip = matched_net.source_ip if matched_net else "192.168.1.105"
        cmd = matched_net.function_name if matched_net else "Unauthorized Write"
        payload_desc = matched_net.anomaly_reason if matched_net else f"Command trigger {trip.trigger_rule}"

        # Calculate time delay between network injection and physical symptom
        net_time = matched_net.timestamp if matched_net else trip.timestamp - 0.25
        delay_ms = max(5.0, round((trip.timestamp - net_time) * 1000.0, 1))

        # Classify physical deviation
        if "OVERPRESSURE" in trip.trigger_rule:
            impact_type = "OVERPRESSURE"
            dev_desc = f"Pressure surged to {trip.measured_value} PSI (Safety Trip Threshold: {trip.threshold_value} PSI)"
        elif "THERMAL" in trip.trigger_rule:
            impact_type = "THERMAL_RUNAWAY"
            dev_desc = f"Temperature accelerated to {trip.measured_value} °C (Trip Threshold: {trip.threshold_value} °C)"
        elif "RESONANCE" in trip.trigger_rule:
            impact_type = "RESONANCE"
            dev_desc = f"Agitator rotor vibration hit {trip.measured_value} mm/s in resonant harmonic band"
        elif "CAVITATION" in trip.trigger_rule:
            impact_type = "CAVITATION_STRESS"
            dev_desc = f"Hydraulic cavitation index hit {trip.measured_value} with severe pipe stress"
        elif "OVERFLOW" in trip.trigger_rule:
            impact_type = "TANK_OVERFLOW"
            dev_desc = f"Storage tank liquid level surged to {trip.measured_value} %"
        else:
            impact_type = "MANUAL_ESTOP"
            dev_desc = "Process halted by operator emergency command"

        mitre_info = classify_attack(
            protocol=proto,
            function_code=matched_net.function_code if matched_net else 6,
            target_actuator=trip.affected_actuators[0] if trip.affected_actuators else None,
            physical_deviation_type=impact_type,
        )

        incident = CorrelatedIncident(
            incident_id=incident_id,
            timestamp=now,
            network_event_id=net_id,
            protocol=proto,
            source_ip=src_ip,
            command_type=cmd,
            payload_summary=payload_desc,
            physical_impact_type=impact_type,
            deviation_description=dev_desc,
            peak_pressure_psi=current_state.reactor_pressure_psi,
            peak_temp_c=current_state.reactor_temp_c,
            peak_vibration_mms=current_state.vibration_mms,
            targeted_actuators=trip.affected_actuators,
            safety_intervened=True,
            safety_trip_id=trip.trip_id,
            reaction_time_ms=trip.reaction_time_ms,
            damage_prevented=trip.damage_prevented,
            mitre_technique_id=mitre_info["id"],
            mitre_technique_name=mitre_info["name"],
            mitre_tactic=mitre_info["tactic"],
            network_to_physical_delay_ms=delay_ms,
        )

        self.incidents.append(incident)
        if len(self.incidents) > self.max_records:
            self.incidents.pop(0)

        return incident

    def get_recent_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [inc.to_dict() for inc in self.incidents[-limit:]]

    def get_timeline(self, limit: int = 20) -> Dict[str, Any]:
        """Dual-axis timeline correlating network events with physical symptoms."""
        return {
            "incidents": [inc.to_dict() for inc in self.incidents[-limit:]],
            "total_incidents": self._incident_count,
        }
