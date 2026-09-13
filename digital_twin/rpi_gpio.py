"""
Raspberry Pi GPIO and Hardware Abstraction Layer (HAL).
Enables the digital twin to control real hardware relays, LEDs, and motor drivers
when deployed on a Raspberry Pi, while seamlessly operating in high-fidelity
virtualized simulation mode on standard development workstations.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("CPH-TM.HAL")

# Standard BCM Pin Mapping for 12 Actuators & Status LEDs
PIN_MAP = {
    "ACT-01": 17,  # Primary Feed Pump Relay / PWM
    "ACT-02": 18,  # Inflow Valve PWM (Hardware PWM0)
    "ACT-03": 27,  # Acid Dosing Pump
    "ACT-04": 22,  # Base Neutralizer Pump
    "ACT-05": 19,  # Agitator PWM (Hardware PWM1)
    "ACT-06": 23,  # Main Heating Triac
    "ACT-07": 24,  # Cooling Jacket Valve
    "ACT-08": 25,  # Secondary Transfer Pump
    "ACT-09": 12,  # Filter Backwash Solenoid
    "ACT-10": 13,  # Emergency Relief Valve (Fail-safe)
    "ACT-11": 16,  # Bottom Drain Solenoid
    "ACT-12": 26,  # Scrubber Damper Servo
    "LED_SYS_OK": 5,
    "LED_TRIP": 6,
    "BUZZER_ALARM": 21,
}

class HardwareInterface:
    """Hardware abstraction for Raspberry Pi GPIO with virtual fallback."""

    def __init__(self, force_virtual: bool = False):
        self.is_physical_pi = False
        self.virtual_pins: Dict[int, Dict[str, Any]] = {}
        self._gpio_module = None

        # Initialize pin records
        for name, pin in PIN_MAP.items():
            self.virtual_pins[pin] = {
                "name": name,
                "pin": pin,
                "mode": "OUT",
                "state": 0,
                "pwm_duty": 0.0,
                "is_isolated": False,
            }

        if not force_virtual:
            try:
                import RPi.GPIO as GPIO  # type: ignore
                self._gpio_module = GPIO
                self._gpio_module.setmode(GPIO.BCM)
                self._gpio_module.setwarnings(False)
                for pin in PIN_MAP.values():
                    self._gpio_module.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                self.is_physical_pi = True
                logger.info("Native Raspberry Pi GPIO hardware detected and initialized.")
            except (ImportError, RuntimeError):
                self.is_physical_pi = False
                logger.info("Standard PC / VM environment: running in virtualized hardware sandbox mode.")

    def set_actuator_output(self, actuator_id: str, value: float, is_isolated: bool = False) -> None:
        """Drive pin or update virtual register."""
        pin = PIN_MAP.get(actuator_id)
        if pin is None:
            return

        clamped_val = max(0.0, min(100.0, float(value)))
        if is_isolated:
            effective_val = 0.0
            digital_state = 0
        else:
            effective_val = clamped_val
            digital_state = 1 if effective_val > 0 else 0

        self.virtual_pins[pin]["state"] = digital_state
        self.virtual_pins[pin]["pwm_duty"] = effective_val
        self.virtual_pins[pin]["is_isolated"] = is_isolated

        if self.is_physical_pi and self._gpio_module:
            try:
                self._gpio_module.output(pin, digital_state)
            except Exception as e:
                logger.error(f"GPIO write error on pin {pin}: {e}")

    def set_safety_trip_indicators(self, tripped: bool) -> None:
        """Drive physical or virtual indicator LEDs / buzzer."""
        ok_pin = PIN_MAP["LED_SYS_OK"]
        trip_pin = PIN_MAP["LED_TRIP"]
        buzzer_pin = PIN_MAP["BUZZER_ALARM"]

        self.virtual_pins[ok_pin]["state"] = 0 if tripped else 1
        self.virtual_pins[trip_pin]["state"] = 1 if tripped else 0
        self.virtual_pins[buzzer_pin]["state"] = 1 if tripped else 0

        if self.is_physical_pi and self._gpio_module:
            try:
                self._gpio_module.output(ok_pin, 0 if tripped else 1)
                self._gpio_module.output(trip_pin, 1 if tripped else 0)
                self._gpio_module.output(buzzer_pin, 1 if tripped else 0)
            except Exception:
                pass

    def get_hardware_state(self) -> Dict[str, Any]:
        """Return status dictionary of all pins and hardware environment."""
        return {
            "is_physical_pi": self.is_physical_pi,
            "platform": "Raspberry Pi GPIO" if self.is_physical_pi else "Virtualized Hardware Sandbox",
            "pin_count": len(self.virtual_pins),
            "pins": {v["name"]: v for v in self.virtual_pins.values()},
        }

    def cleanup(self) -> None:
        if self.is_physical_pi and self._gpio_module:
            try:
                self._gpio_module.cleanup()
            except Exception:
                pass
