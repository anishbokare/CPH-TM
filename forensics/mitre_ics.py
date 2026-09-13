"""
MITRE ATT&CK for ICS Knowledge Base & Technique Mapper.
Provides classification, tactics, and impact analysis for industrial attacks.
"""

from typing import Dict, Any, List, Optional


MITRE_ICS_TECHNIQUES: Dict[str, Dict[str, Any]] = {
    "T0855": {
        "id": "T0855",
        "name": "Unauthorized Command Message",
        "tactic": "Impair Process Control",
        "description": "Adversary injects unauthorized command messages (e.g. Modbus FC5/FC6/FC16 or DNP3 Direct Operate) to instruct control systems to perform unauthorized actions.",
        "severity": "HIGH",
    },
    "T0836": {
        "id": "T0836",
        "name": "Modify Parameter",
        "tactic": "Impair Process Control",
        "description": "Adversary modifies setpoints, alarm thresholds, or controller calibration registers to alter physical operating boundaries.",
        "severity": "HIGH",
    },
    "T0814": {
        "id": "T0814",
        "name": "Denial of Service",
        "tactic": "Inhibit Response Function",
        "description": "Adversary floods the fieldbus or SCADA network with high-frequency packets to degrade communication responsiveness.",
        "severity": "MEDIUM",
    },
    "T0831": {
        "id": "T0831",
        "name": "Manipulation of Control",
        "tactic": "Impair Process Control",
        "description": "Adversary manipulates logical control variables or switches actuators continuously to induce mechanical wear, water hammer, or instability.",
        "severity": "CRITICAL",
    },
    "T0879": {
        "id": "T0879",
        "name": "Damage to Property",
        "tactic": "Impact",
        "description": "Adversary drives physical process parameters (pressure, temperature, rotor resonance) past equipment structural limits to cause physical destruction.",
        "severity": "CRITICAL",
    },
    "T0880": {
        "id": "T0880",
        "name": "Loss of Safety",
        "tactic": "Impact",
        "description": "Adversary impairs safety instrumented functions, overrides interlock relays, or disables emergency pressure relief valves.",
        "severity": "CRITICAL",
    },
    "T0806": {
        "id": "T0806",
        "name": "Brute Force I/O",
        "tactic": "Impair Process Control",
        "description": "Adversary scans or toggles multiple coil/register addresses in rapid succession to discover I/O mappings or perturb state.",
        "severity": "MEDIUM",
    },
    "T0853": {
        "id": "T0853",
        "name": "Manipulation of View",
        "tactic": "Impair Process Control",
        "description": "Adversary spoofs sensor values (false data injection) to deceive operators while physical process deviates from safe state.",
        "severity": "HIGH",
    },
}


def classify_attack(
    protocol: str,
    function_code: Optional[int],
    target_actuator: Optional[str],
    physical_deviation_type: Optional[str],
) -> Dict[str, Any]:
    """
    Classify observed cyber-physical activity into MITRE ATT&CK for ICS technique.
    """
    if physical_deviation_type in ("OVERPRESSURE", "THERMAL_RUNAWAY", "RESONANCE"):
        tech = MITRE_ICS_TECHNIQUES["T0879"]
    elif physical_deviation_type == "SAFETY_BYPASS":
        tech = MITRE_ICS_TECHNIQUES["T0880"]
    elif physical_deviation_type == "CAVITATION_STRESS":
        tech = MITRE_ICS_TECHNIQUES["T0831"]
    elif physical_deviation_type == "FALSE_DATA_INJECTION":
        tech = MITRE_ICS_TECHNIQUES["T0853"]
    elif protocol == "MODBUS_TCP" and function_code in (6, 16):
        tech = MITRE_ICS_TECHNIQUES["T0836"]
    elif protocol in ("MODBUS_TCP", "DNP3") and function_code in (5, 15, 0x04, 0x05):
        tech = MITRE_ICS_TECHNIQUES["T0855"]
    elif protocol == "MODBUS_TCP" and function_code in (1, 2, 3, 4):
        tech = MITRE_ICS_TECHNIQUES["T0806"]
    else:
        tech = MITRE_ICS_TECHNIQUES["T0855"]

    return tech
