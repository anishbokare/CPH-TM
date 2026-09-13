"""
Simulation & Attack Validation Subsystem for CPH-TM.
"""

from .attack_catalog import generate_500_scenarios, SCENARIO_ARCHETYPES
from .scenario_runner import ScenarioOrchestrator

__all__ = [
    "generate_500_scenarios",
    "SCENARIO_ARCHETYPES",
    "ScenarioOrchestrator",
]
