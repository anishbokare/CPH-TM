"""
Catalog and Generator for 500+ Parameterized ICS Attack Scenarios.
Generates deterministic, structured adversarial attack vectors spanning 8 distinct
industrial attack archetypes to validate cyber-physical honeynet fidelity,
safety controller intervention, and forensic reconstruction accuracy.
"""

from typing import List, Dict, Any

SCENARIO_ARCHETYPES = [
    {
        "category": "Overpressure Injection",
        "protocol": "MODBUS_TCP",
        "fc": 6,
        "address": 0,
        "target_actuator": "ACT-01",
        "mitre_id": "T0879",
        "mitre_name": "Damage to Property",
        "impact_type": "OVERPRESSURE",
        "description_template": "Adversarial holding register write forcing pressure setpoint to {val} PSI and pump to max head",
    },
    {
        "category": "Thermal Runaway Induction",
        "protocol": "MODBUS_TCP",
        "fc": 6,
        "address": 1,
        "target_actuator": "ACT-06",
        "mitre_id": "T0879",
        "mitre_name": "Damage to Property",
        "impact_type": "THERMAL_RUNAWAY",
        "description_template": "Injected heater command setting thermal load to {val} kW with cooling shutoff",
    },
    {
        "category": "Stuxnet-Style Agitator Resonance",
        "protocol": "MODBUS_TCP",
        "fc": 6,
        "address": 3,
        "target_actuator": "ACT-05",
        "mitre_id": "T0879",
        "mitre_name": "Damage to Property",
        "impact_type": "RESONANCE",
        "description_template": "Harmonic resonance sweep targeting impeller natural frequency at {val} RPM",
    },
    {
        "category": "Cavitation & Water Hammer",
        "protocol": "MODBUS_TCP",
        "fc": 6,
        "address": 5,
        "target_actuator": "ACT-01",
        "mitre_id": "T0831",
        "mitre_name": "Manipulation of Control",
        "impact_type": "CAVITATION_STRESS",
        "description_template": "Rapid valve constriction to {val}% while feed pump is driven at peak velocity",
    },
    {
        "category": "False Data Injection / Tank Overflow",
        "protocol": "MODBUS_TCP",
        "fc": 16,
        "address": 2,
        "target_actuator": "ACT-01",
        "mitre_id": "T0853",
        "mitre_name": "Manipulation of View",
        "impact_type": "TANK_OVERFLOW",
        "description_template": "Spoofed tank telemetry masking level surge while driving feed pump to {val} RPM",
    },
    {
        "category": "DNP3 Rogue Direct Operate",
        "protocol": "DNP3",
        "fc": 0x05,
        "address": 1,
        "target_actuator": "ACT-01",
        "mitre_id": "T0855",
        "mitre_name": "Unauthorized Command Message",
        "impact_type": "OVERPRESSURE",
        "description_template": "Unauthorized DNP3 Direct Operate command forcing primary transfer pump on at {val}%",
    },
    {
        "category": "MQTT Setpoint Tampering",
        "protocol": "MQTT",
        "fc": None,
        "address": None,
        "target_actuator": "ACT-06",
        "mitre_id": "T0836",
        "mitre_name": "Modify Parameter",
        "impact_type": "THERMAL_RUNAWAY",
        "description_template": "IIoT edge publish to scada/override topic with thermal setpoint {val} C",
    },
    {
        "category": "Fieldbus Command Flooding / DoS",
        "protocol": "MODBUS_TCP",
        "fc": 15,
        "address": 0,
        "target_actuator": "ACT-02",
        "mitre_id": "T0814",
        "mitre_name": "Denial of Service",
        "impact_type": "CAVITATION_STRESS",
        "description_template": "High-frequency coil burst storm pulsing actuators with cycle time {val} ms",
    },
]


def generate_500_scenarios(count: int = 500) -> List[Dict[str, Any]]:
    """
    Generate 500+ uniquely parameterized industrial attack scenarios.
    """
    scenarios: List[Dict[str, Any]] = []
    attacker_ips = [
        "192.168.1.105", "10.0.4.88", "172.16.20.12", "198.51.100.42",
        "203.0.113.19", "185.220.101.5", "91.240.118.17", "45.154.255.89"
    ]

    for i in range(count):
        archetype_idx = i % len(SCENARIO_ARCHETYPES)
        arch = SCENARIO_ARCHETYPES[archetype_idx]
        scenario_num = i + 1
        scenario_id = f"SCN-{scenario_num:04d}"

        # Parameter variation based on scenario index
        if arch["category"] == "Overpressure Injection":
            param_val = 850 + (i % 15) * 10   # 85 to 100 PSI (register scaled x10)
        elif arch["category"] == "Thermal Runaway Induction":
            param_val = 11.0 + (i % 5) * 1.0  # 11 to 15 kW
        elif arch["category"] == "Stuxnet-Style Agitator Resonance":
            param_val = 1460 + (i % 9) * 10   # 1460 to 1540 RPM
        elif arch["category"] == "Cavitation & Water Hammer":
            param_val = 5.0 + (i % 6) * 2.0   # 5 to 15% valve opening
        elif arch["category"] == "False Data Injection / Tank Overflow":
            param_val = 3200 + (i % 5) * 80   # 3200 to 3600 RPM
        elif arch["category"] == "DNP3 Rogue Direct Operate":
            param_val = 100
        elif arch["category"] == "MQTT Setpoint Tampering":
            param_val = 92.0 + (i % 8) * 1.5
        else:
            param_val = 50 + (i % 10) * 10

        src_ip = attacker_ips[i % len(attacker_ips)]
        desc = arch["description_template"].format(val=param_val)

        scenario = {
            "scenario_id": scenario_id,
            "category": arch["category"],
            "protocol": arch["protocol"],
            "function_code": arch["fc"],
            "address": arch["address"],
            "parameter_value": param_val,
            "source_ip": src_ip,
            "target_actuator": arch["target_actuator"],
            "mitre_id": arch["mitre_id"],
            "mitre_name": arch["mitre_name"],
            "impact_type": arch["impact_type"],
            "description": desc,
            "complexity": "Tier-1" if i % 3 == 0 else ("Tier-2" if i % 3 == 1 else "Tier-3 Advanced APT"),
        }
        scenarios.append(scenario)

    return scenarios
