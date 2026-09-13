"""
Dynamic Physical Process Model for the Industrial Digital Twin.
Simulates a hydro-chemical water purification and pressurized reaction vessel
with coupled thermodynamics, fluid dynamics, chemical equilibria,
mechanical resonance, and cavitation models.
"""

import math
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from .actuators import ActuatorBank
from .rpi_gpio import HardwareInterface


@dataclass
class PhysicalProcessState:
    timestamp: float
    # Storage & Fluid levels (0 - 100 %)
    tank_level_pct: float = 62.5
    reactor_level_pct: float = 58.0
    inflow_rate_lpm: float = 120.0
    outflow_rate_lpm: float = 118.0

    # Thermodynamics & Pressure
    reactor_pressure_psi: float = 48.5
    reactor_temp_c: float = 64.2
    cooling_jacket_temp_c: float = 22.0

    # Chemical metrics
    ph_level: float = 7.15
    conductivity_us_cm: float = 450.0

    # Mechanical & Integrity metrics
    vibration_mms: float = 1.2
    cavitation_index: float = 0.0  # 0.0 (smooth) to 1.0 (severe destructive cavitation)
    pipe_stress_kpa: float = 320.0

    # Process status flags
    is_overpressure_warning: bool = False
    is_overpressure_critical: bool = False
    is_thermal_runaway: bool = False
    is_resonance_lock: bool = False
    is_cavitation_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcessDigitalTwin:
    """Real-time physical process simulator coupled to the 12-actuator bank."""

    def __init__(
        self,
        actuator_bank: Optional[ActuatorBank] = None,
        hardware: Optional[HardwareInterface] = None,
    ):
        self.actuators = actuator_bank or ActuatorBank()
        self.hardware = hardware or HardwareInterface()
        self.state = PhysicalProcessState(timestamp=time.time())

        # Baseline steady-state setpoints
        self.ambient_temp = 21.0
        self.last_step_time = time.time()
        self.history: List[Dict[str, Any]] = []
        self.max_history = 600

    def step(self, dt: Optional[float] = None) -> PhysicalProcessState:
        """Advance the cyber-physical process by dt seconds."""
        now = time.time()
        if dt is None:
            dt = max(0.01, min(0.5, now - self.last_step_time))
        self.last_step_time = now

        # 1. Advance actuator electromechanics
        self.actuators.step(dt)
        acts = self.actuators.actuators

        # Actuator values
        pump1_rpm = acts["ACT-01"].current_value
        inflow_valve_pct = acts["ACT-02"].current_value / 100.0
        acid_pct = acts["ACT-03"].current_value / 100.0
        base_pct = acts["ACT-04"].current_value / 100.0
        agitator_rpm = acts["ACT-05"].current_value
        heater_kw = acts["ACT-06"].current_value
        cooling_pct = acts["ACT-07"].current_value / 100.0
        transfer_rpm = acts["ACT-08"].current_value
        relief_valve_pct = acts["ACT-10"].current_value / 100.0
        drain_pct = acts["ACT-11"].current_value / 100.0
        damper_pct = acts["ACT-12"].current_value / 90.0

        # Update Raspberry Pi / Virtual HAL outputs
        for act_id, act in acts.items():
            self.hardware.set_actuator_output(act_id, act.current_value, act.is_isolated)

        # 2. Fluid Flow & Tank Levels
        # Feed pump delivers flow constrained by inflow valve position
        raw_inflow = (pump1_rpm / 3600.0) * 250.0 * inflow_valve_pct
        outflow = (transfer_rpm / 3000.0) * 220.0 + (drain_pct * 80.0)

        # Tank mass balance
        d_tank = (raw_inflow - outflow * 0.9) * (dt / 120.0)
        self.state.tank_level_pct = max(0.0, min(100.0, self.state.tank_level_pct + d_tank))
        self.state.inflow_rate_lpm = round(raw_inflow, 2)
        self.state.outflow_rate_lpm = round(outflow, 2)

        # Reactor liquid level
        d_reactor = (outflow * 0.9 - (transfer_rpm / 3000.0) * 180.0) * (dt / 100.0)
        self.state.reactor_level_pct = max(0.0, min(100.0, self.state.reactor_level_pct + d_reactor))

        # 3. Chemical Reaction Kinetics & Thermodynamics
        # Exothermic heat generation: proportional to reactor level and agitator mixing
        reaction_heat_gen = (self.state.reactor_level_pct / 100.0) * 4.5 * (agitator_rpm / 1800.0)
        heater_input = heater_kw * 1.8  # kW to heat transfer equivalent
        cooling_removal = cooling_pct * 14.0 * ((self.state.reactor_temp_c - self.state.cooling_jacket_temp_c) / 40.0)
        ambient_loss = 0.08 * (self.state.reactor_temp_c - self.ambient_temp)

        d_temp = (reaction_heat_gen + heater_input - cooling_removal - ambient_loss) * dt
        self.state.reactor_temp_c = round(max(15.0, min(150.0, self.state.reactor_temp_c + d_temp)), 2)

        # 4. Pressure Vessel Dynamics
        # Pressure increases with vapor pressure from temperature + pump head - relief valve exhaust
        vapor_pressure = 14.7 * math.exp(0.028 * (self.state.reactor_temp_c - 20.0))
        hydraulic_head = (pump1_rpm / 3600.0) * 28.0
        relief_exhaust = relief_valve_pct * 95.0
        damper_vent = damper_pct * 15.0

        target_pressure = vapor_pressure + hydraulic_head - relief_exhaust - damper_vent
        d_press = (target_pressure - self.state.reactor_pressure_psi) * 0.8 * dt
        self.state.reactor_pressure_psi = round(max(0.0, min(160.0, self.state.reactor_pressure_psi + d_press)), 2)

        # 5. pH Chemistry (Acid vs Base)
        d_ph = (base_pct * 1.5 - acid_pct * 1.8) * dt * 0.15
        # Natural buffering pull towards 7.0
        d_ph += (7.0 - self.state.ph_level) * 0.02 * dt
        self.state.ph_level = round(max(1.0, min(14.0, self.state.ph_level + d_ph)), 2)

        # 6. Mechanical Resonance & Vibration (Stuxnet Attack Profile)
        # Resonant harmonic range for agitator ACT-05: 1420 - 1580 RPM
        if 1420.0 <= agitator_rpm <= 1580.0:
            self.state.is_resonance_lock = True
            resonance_intensity = 1.0 - abs(agitator_rpm - 1500.0) / 80.0
            d_vib = (14.0 * resonance_intensity - self.state.vibration_mms) * 2.0 * dt
        else:
            self.state.is_resonance_lock = False
            baseline_vib = 1.0 + (pump1_rpm / 3600.0) * 1.5 + (agitator_rpm / 1800.0) * 1.0
            d_vib = (baseline_vib - self.state.vibration_mms) * dt
        self.state.vibration_mms = round(max(0.2, self.state.vibration_mms + d_vib), 2)

        # 7. Cavitation & Pipe Stress
        # Cavitation happens if feed pump runs high while inflow valve is choked (< 15%)
        if pump1_rpm > 2200.0 and inflow_valve_pct < 0.20:
            self.state.is_cavitation_active = True
            self.state.cavitation_index = min(1.0, self.state.cavitation_index + 0.5 * dt)
        else:
            self.state.is_cavitation_active = False
            self.state.cavitation_index = max(0.0, self.state.cavitation_index - 0.8 * dt)

        self.state.pipe_stress_kpa = round(
            280.0 + self.state.reactor_pressure_psi * 3.5 + self.state.cavitation_index * 180.0, 1
        )

        # 8. Anomaly & Safety Threshold Evaluation
        self.state.is_overpressure_warning = (self.state.reactor_pressure_psi >= 68.0)
        self.state.is_overpressure_critical = (self.state.reactor_pressure_psi >= 85.0)
        self.state.is_thermal_runaway = (self.state.reactor_temp_c >= 88.0)

        self.state.timestamp = now

        # Append to telemetry history ring buffer
        self.history.append(self.state.to_dict())
        if len(self.history) > self.max_history:
            self.history.pop(0)

        return self.state

    def mirror_network_write(self, command: Dict[str, Any]) -> None:
        """
        Mirror an adversarial Modbus/DNP3 write into the digital twin process.
        """
        source = command.get("source", "UNKNOWN")
        addr = command.get("address")
        val = command.get("value")

        if source == "MODBUS_TCP":
            # Map Modbus Holding Registers / Coils to Actuators
            # Register 0: Pressure setpoint override
            # Register 1: Temperature / Heater setpoint
            # Register 2: Feed Pump Speed (ACT-01)
            # Register 3: Agitator Speed (ACT-05)
            # Register 4: Acid Dosing (ACT-03)
            # Register 5: Inflow Valve (ACT-02)
            if addr == 0:  # Direct pressure manipulation / compressor injection
                pass  # Setpoint tracked by PLC
            elif addr == 1:
                # Target temperature: heater driven proportionally
                heater_target = max(0.0, min(15.0, (float(val) / 10.0 - 50.0) * 0.4))
                self.actuators.set_target("ACT-06", heater_target)
            elif addr == 2:
                self.actuators.set_target("ACT-01", float(val))
            elif addr == 3:
                self.actuators.set_target("ACT-05", float(val))
            elif addr == 4:
                self.actuators.set_target("ACT-03", float(val) / 10.0)
            elif addr == 5:
                self.actuators.set_target("ACT-02", float(val))

            # Coils (FC5 / FC15)
            elif addr == 7:  # Cooling valve override (0 = close cooling)
                self.actuators.set_target("ACT-07", 0.0 if not val else 100.0)
            elif addr == 10: # Emergency relief valve
                self.actuators.set_target("ACT-10", 100.0 if val else 0.0)

        elif source == "DNP3":
            # DNP3 Direct Operate
            if addr == 1:
                # Force pump ACT-01 to max or 0
                self.actuators.set_target("ACT-01", 3600.0 if val else 0.0)

        elif source == "MQTT":
            topic = command.get("topic", "")
            try:
                numeric_val = float(command.get("value", 0))
                if "pump" in topic:
                    self.actuators.set_target("ACT-01", numeric_val)
                elif "heater" in topic:
                    self.actuators.set_target("ACT-06", numeric_val)
                elif "valve" in topic:
                    self.actuators.set_target("ACT-02", numeric_val)
            except ValueError:
                pass

    def get_full_telemetry(self) -> Dict[str, Any]:
        """Return unified digital twin status snapshot."""
        return {
            "physical_state": self.state.to_dict(),
            "actuators": self.actuators.get_states(),
            "hardware": self.hardware.get_hardware_state(),
            "timestamp": time.time(),
        }

    def reset_process(self) -> None:
        """Reset physical process and actuators to baseline safe operating conditions."""
        self.actuators.restore_all()
        self.state = PhysicalProcessState(
            timestamp=time.time(),
            tank_level_pct=62.5,
            reactor_level_pct=58.0,
            inflow_rate_lpm=120.0,
            outflow_rate_lpm=118.0,
            reactor_pressure_psi=48.5,
            reactor_temp_c=64.2,
            cooling_jacket_temp_c=22.0,
            ph_level=7.15,
            conductivity_us_cm=450.0,
            vibration_mms=1.2,
            cavitation_index=0.0,
            pipe_stress_kpa=320.0,
        )
        self.hardware.set_safety_trip_indicators(False)
