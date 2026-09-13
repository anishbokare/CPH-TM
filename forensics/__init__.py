"""
Forensics and Cross-Domain Correlation Subsystem for CPH-TM.
"""

from .mitre_ics import MITRE_ICS_TECHNIQUES, classify_attack
from .correlator import ForensicCorrelator, CorrelatedIncident
from .reconstruction import AttackReconstructionEngine, ReconstructionResult

__all__ = [
    "MITRE_ICS_TECHNIQUES",
    "classify_attack",
    "ForensicCorrelator",
    "CorrelatedIncident",
    "AttackReconstructionEngine",
    "ReconstructionResult",
]
