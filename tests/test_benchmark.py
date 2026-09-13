"""
Integration test for the 500-Scenario Attack Validation Suite.
Asserts >=95% reconstruction accuracy across 500 distinct ICS attack vectors.
"""

import pytest
from simulation.scenario_runner import ScenarioOrchestrator
from simulation.attack_catalog import generate_500_scenarios


def test_500_scenario_benchmark_accuracy():
    orchestrator = ScenarioOrchestrator()
    summary = orchestrator.run_benchmark(count=500, fast_mode=True)

    assert summary["total_scenarios_run"] == 500
    metrics = summary["forensic_reconstruction"]

    # Prompt requirement: >= 95% attack reconstruction accuracy
    assert metrics["accuracy_pct"] >= 95.0
    assert metrics["precision_pct"] >= 90.0
    assert metrics["recall_pct"] >= 90.0
    assert metrics["f1_score"] >= 0.90

    # Prompt requirement: Safety controller prevents physical damage
    safety_stats = summary["safety_controller"]
    assert safety_stats["damage_prevented_rate_pct"] > 80.0
    assert safety_stats["mean_reaction_time_ms"] < 25.0
