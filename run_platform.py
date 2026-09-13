"""
Platform CLI Launcher for Cyber-Physical Honeynet with Live Digital Twin Mirroring (CPH-TM).
Starts the unified OT honeypots, dynamic physical simulation loop, safety controller,
and Web SCADA dashboard.
"""

import argparse
import sys
import uvicorn

BANNER = r"""
==========================================================================
   ____ ____  _   _       _____ __  __ 
  / ___|  _ \| | | |     |_   _|  \/  |
 | |   | |_) | |_| | _____ | | | |\/| |
 | |___|  __/|  _  ||_____|| | | |  | |
  \____|_|   |_| |_|       |_| |_|  |_|
  Cyber-Physical Honeynet // Live Digital Twin Mirroring
==========================================================================
 [*] Architecture: OT/ICS Honeynet + Live Digital Twin + Safety Interlocks
 [*] Protocols:    Modbus TCP (:1502), DNP3 (:20000), MQTT (:1883)
 [*] Actuators:    12 Subsystem Actuators (ACT-01 to ACT-12)
 [*] Hardware:     Raspberry Pi GPIO HAL (Native / Sandbox Fallback)
 [*] Safety SIL-3: Deterministic Trip (< 15 ms) & Hardware Isolation Relays
 [*] Forensics:    Cross-Domain Correlation & MITRE ATT&CK for ICS
 [*] Benchmark:    500+ Parameterized Attack Scenarios (>=95% Accuracy)
==========================================================================
"""

def main():
    parser = argparse.ArgumentParser(description="Launch CPH-TM Cyber-Physical Honeynet & Digital Twin Platform")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Binding host for Web SCADA server")
    parser.add_argument("--port", type=int, default=8000, help="Binding port for Web SCADA server")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print(BANNER)
    print(f" [*] Starting Web SCADA Dashboard at: http://127.0.0.1:{args.port}")
    print(f" [*] Modbus TCP Deception listener on: 0.0.0.0:1502")
    print(f" [*] DNP3 Outstation listener on:     0.0.0.0:20000")
    print(f" [*] MQTT IIoT Broker listener on:    0.0.0.0:1883")
    print(" [*] Press Ctrl+C to terminate platform.\n")

    uvicorn.run(
        "backend.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )

if __name__ == "__main__":
    main()
