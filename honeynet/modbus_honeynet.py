"""
Asynchronous Modbus TCP Honeynet Server.
Emulates an industrial Schneider Modicon M340 / Siemens S7 PLC.
Captures adversarial Modbus traffic, decodes standard industrial function codes,
and mirrors writes directly into the Digital Twin physics process.
"""

import asyncio
import struct
import socket
from typing import Dict, Any, Optional, Callable
from .packet_logger import PacketLogger, NetworkEvent

# Function code names
FC_NAMES = {
    1: "Read Coils",
    2: "Read Discrete Inputs",
    3: "Read Holding Registers",
    4: "Read Input Registers",
    5: "Write Single Coil",
    6: "Write Single Register",
    15: "Write Multiple Coils",
    16: "Write Multiple Registers",
    43: "Read Device Identification",
}

class ModbusHoneynetServer:
    """Modbus TCP Honeypot listener that mirrors operations to the Digital Twin."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 1502,
        logger: Optional[PacketLogger] = None,
        twin_mirror_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.host = host
        self.port = port
        self.logger = logger or PacketLogger()
        self.twin_mirror_callback = twin_mirror_callback
        self.server: Optional[asyncio.Server] = None
        self.is_running = False

        # Virtual PLC memory tables
        self.coils: Dict[int, bool] = {i: False for i in range(128)}
        self.discrete_inputs: Dict[int, bool] = {i: False for i in range(128)}
        self.holding_registers: Dict[int, int] = {i: 0 for i in range(128)}
        self.input_registers: Dict[int, int] = {i: 0 for i in range(128)}

        # Baseline industrial setpoints (Schneider M340 profile)
        self.holding_registers[0] = 500   # Reactor Pressure Setpoint (50.0 PSI)
        self.holding_registers[1] = 650   # Temperature Target (65.0 C)
        self.holding_registers[2] = 1800  # Feed Pump Speed (1800 RPM)
        self.holding_registers[3] = 1200  # Agitator Motor Speed (1200 RPM)
        self.holding_registers[4] = 450   # Acid Dosing Rate (45.0 mL/min)
        self.holding_registers[5] = 50    # Valve Position % (50%)

    async def start(self) -> None:
        """Start async Modbus TCP socket listener."""
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.is_running = True

    async def stop(self) -> None:
        """Stop server."""
        self.is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        client_ip = addr[0] if addr else "127.0.0.1"
        client_port = addr[1] if addr else 0

        try:
            while self.is_running:
                # Modbus TCP MBAP Header is 7 bytes:
                # Transaction ID (2), Protocol ID (2, must be 0), Length (2), Unit ID (1)
                header = await reader.readexactly(7)
                if not header:
                    break

                trans_id, proto_id, length, unit_id = struct.unpack(">HHHB", header)
                if proto_id != 0:
                    # Not standard Modbus TCP
                    break

                pdu_len = length - 1
                pdu = await reader.readexactly(pdu_len)
                if not pdu:
                    break

                response_pdu, event_info = self._process_pdu(pdu, unit_id, client_ip, client_port)

                # Log network event
                if event_info:
                    raw_hex = (header + pdu).hex()
                    evt = self.logger.create_and_log(
                        protocol="MODBUS_TCP",
                        source_ip=client_ip,
                        source_port=client_port,
                        dest_ip=self.host,
                        dest_port=self.port,
                        function_code=event_info.get("fc"),
                        function_name=event_info.get("fc_name"),
                        unit_id=unit_id,
                        address=event_info.get("address"),
                        value=event_info.get("value"),
                        raw_payload_hex=raw_hex,
                        is_anomaly=event_info.get("is_anomaly", False),
                        anomaly_reason=event_info.get("anomaly_reason"),
                        metadata={
                            "trans_id": trans_id,
                            "length": length,
                            "details": event_info.get("details", {}),
                        },
                    )

                    # Mirror write commands directly to digital twin
                    if event_info.get("is_write") and self.twin_mirror_callback:
                        self.twin_mirror_callback({
                            "source": "MODBUS_TCP",
                            "fc": event_info.get("fc"),
                            "address": event_info.get("address"),
                            "value": event_info.get("value"),
                            "client_ip": client_ip,
                            "network_event_id": evt.event_id,
                        })

                # Build MBAP response
                resp_length = len(response_pdu) + 1
                resp_header = struct.pack(">HHHB", trans_id, 0, resp_length, unit_id)
                writer.write(resp_header + response_pdu)
                await writer.drain()

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _process_pdu(self, pdu: bytes, unit_id: int, client_ip: str, client_port: int):
        fc = pdu[0]
        data = pdu[1:]
        fc_name = FC_NAMES.get(fc, f"Unknown FC {fc}")
        event_info = {
            "fc": fc,
            "fc_name": fc_name,
            "is_write": False,
            "is_anomaly": False,
            "details": {},
        }

        # FC 1: Read Coils
        if fc == 1:
            addr, count = struct.unpack(">HH", data[0:4])
            event_info["address"] = addr
            event_info["value"] = count
            byte_count = (count + 7) // 8
            coil_bytes = bytearray(byte_count)
            for i in range(count):
                coil_val = self.coils.get(addr + i, False)
                if coil_val:
                    coil_bytes[i // 8] |= (1 << (i % 8))
            return bytes([fc, byte_count]) + bytes(coil_bytes), event_info

        # FC 2: Read Discrete Inputs
        elif fc == 2:
            addr, count = struct.unpack(">HH", data[0:4])
            event_info["address"] = addr
            event_info["value"] = count
            byte_count = (count + 7) // 8
            in_bytes = bytearray(byte_count)
            for i in range(count):
                if self.discrete_inputs.get(addr + i, False):
                    in_bytes[i // 8] |= (1 << (i % 8))
            return bytes([fc, byte_count]) + bytes(in_bytes), event_info

        # FC 3: Read Holding Registers
        elif fc == 3:
            addr, count = struct.unpack(">HH", data[0:4])
            event_info["address"] = addr
            event_info["value"] = count
            byte_count = count * 2
            reg_bytes = bytearray()
            for i in range(count):
                reg_val = self.holding_registers.get(addr + i, 0)
                reg_bytes.extend(struct.pack(">H", reg_val & 0xFFFF))
            return bytes([fc, byte_count]) + bytes(reg_bytes), event_info

        # FC 4: Read Input Registers
        elif fc == 4:
            addr, count = struct.unpack(">HH", data[0:4])
            event_info["address"] = addr
            event_info["value"] = count
            byte_count = count * 2
            reg_bytes = bytearray()
            for i in range(count):
                reg_val = self.input_registers.get(addr + i, 0)
                reg_bytes.extend(struct.pack(">H", reg_val & 0xFFFF))
            return bytes([fc, byte_count]) + bytes(reg_bytes), event_info

        # FC 5: Write Single Coil
        elif fc == 5:
            addr, val_code = struct.unpack(">HH", data[0:4])
            val_bool = (val_code == 0xFF00)
            self.coils[addr] = val_bool
            event_info["address"] = addr
            event_info["value"] = val_bool
            event_info["is_write"] = True

            # Anomaly heuristic: Critical interlock coils or rapid toggling
            if addr in (0, 1, 2, 7, 9, 10):  # Critical emergency coils
                event_info["is_anomaly"] = True
                event_info["anomaly_reason"] = f"Adversarial write to safety coil #{addr} ({val_bool})"
            return pdu[:5], event_info

        # FC 6: Write Single Register
        elif fc == 6:
            addr, val = struct.unpack(">HH", data[0:4])
            self.holding_registers[addr] = val
            event_info["address"] = addr
            event_info["value"] = val
            event_info["is_write"] = True

            # Anomaly heuristic: Dangerous setpoints (e.g. pressure > 100 PSI, temp > 95 C, pump > 3200 RPM)
            if addr == 0 and val > 800:  # Pressure > 80 PSI
                event_info["is_anomaly"] = True
                event_info["anomaly_reason"] = f"Dangerous pressure setpoint injection ({val / 10.0:.1f} PSI)"
            elif addr == 1 and val > 900:  # Temp > 90 C
                event_info["is_anomaly"] = True
                event_info["anomaly_reason"] = f"Thermal runaway temperature setpoint injection ({val / 10.0:.1f} C)"
            elif addr == 2 and val > 3000:  # Pump > 3000 RPM
                event_info["is_anomaly"] = True
                event_info["anomaly_reason"] = f"Motor overspeed cavitation setpoint ({val} RPM)"
            else:
                event_info["is_anomaly"] = True
                event_info["anomaly_reason"] = f"Unauthorized holding register write to reg #{addr} = {val}"

            return pdu[:5], event_info

        # FC 15: Write Multiple Coils
        elif fc == 15:
            addr, count, byte_count = struct.unpack(">HHB", data[0:5])
            raw_vals = data[5:5 + byte_count]
            vals = []
            for i in range(count):
                b = raw_vals[i // 8]
                v = bool(b & (1 << (i % 8)))
                self.coils[addr + i] = v
                vals.append(v)
            event_info["address"] = addr
            event_info["value"] = vals
            event_info["is_write"] = True
            event_info["is_anomaly"] = True
            event_info["anomaly_reason"] = f"Bulk coil manipulation across {count} coils starting at {addr}"
            return bytes([fc]) + data[0:4], event_info

        # FC 16: Write Multiple Registers
        elif fc == 16:
            addr, count, byte_count = struct.unpack(">HHB", data[0:5])
            vals = []
            for i in range(count):
                val = struct.unpack(">H", data[5 + i * 2 : 7 + i * 2])[0]
                self.holding_registers[addr + i] = val
                vals.append(val)
            event_info["address"] = addr
            event_info["value"] = vals
            event_info["is_write"] = True
            event_info["is_anomaly"] = True
            event_info["anomaly_reason"] = f"Bulk register injection across {count} holding registers"
            return bytes([fc]) + data[0:4], event_info

        # FC 43: Device Identification (Schneider Electric M340)
        elif fc == 43:
            # Emulate authentic vendor response
            mei_type = data[0] if len(data) > 0 else 0x0E
            vendor_pdu = bytes([
                0x2B, 0x0E, 0x01, 0x83, 0x00, 0x00, 0x03,
                0x00, len("Schneider Electric"), *b"Schneider Electric",
                0x01, len("BMX P34 2020"), *b"BMX P34 2020",
                0x02, len("V03.20"), *b"V03.20",
            ])
            event_info["details"]["action"] = "Reconnaissance / PLC Device Fingerprint"
            return vendor_pdu, event_info

        # Unsupported / Exception Response (Error code = FC + 0x80, Exception Code 0x01: Illegal Function)
        return bytes([fc + 0x80, 0x01]), event_info
