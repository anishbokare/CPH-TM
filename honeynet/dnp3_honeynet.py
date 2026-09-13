"""
DNP3 (Distributed Network Protocol 3) Outstation Honeynet Server.
Emulates an electrical substation / water utility RTU outstation on port 20000.
Captures malicious DNP3 Direct Operate, CROB (Control Relay Output Block),
and Analog Output commands and mirrors them into the Digital Twin.
"""

import asyncio
import struct
from typing import Dict, Any, Optional, Callable
from .packet_logger import PacketLogger

DNP3_FC_NAMES = {
    0x00: "Confirm",
    0x01: "Read",
    0x02: "Write",
    0x03: "Select",
    0x04: "Operate",
    0x05: "Direct Operate",
    0x06: "Direct Operate No Ack",
    0x0E: "Cold Restart",
    0x0F: "Warm Restart",
    0x14: "Enable Unsolicited",
    0x15: "Disable Unsolicited",
    0x81: "Response",
}

class DNP3HoneynetServer:
    """Async DNP3 Outstation honeynet server."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 20000,
        logger: Optional[PacketLogger] = None,
        twin_mirror_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.host = host
        self.port = port
        self.logger = logger or PacketLogger()
        self.twin_mirror_callback = twin_mirror_callback
        self.server: Optional[asyncio.Server] = None
        self.is_running = False

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.is_running = True

    async def stop(self) -> None:
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
                # DNP3 Data Link Header: 10 bytes minimum
                # Sync: 0x05 0x64, Length: 1B, Control: 1B, Dest: 2B, Src: 2B, CRC: 2B
                header = await reader.read(10)
                if not header or len(header) < 10:
                    break

                if header[0] != 0x05 or header[1] != 0x64:
                    # Not standard DNP3 frame sync
                    break

                frame_len = header[2]  # bytes following length field minus CRCs
                payload = await reader.read(frame_len + 16)
                full_frame = header + payload

                # Parse application layer (typically follows transport header)
                # Transport header (1B), App Control (1B), App Function Code (1B)
                app_fc = 0x01
                if len(payload) >= 3:
                    app_fc = payload[2]

                fc_name = DNP3_FC_NAMES.get(app_fc, f"Unknown DNP3 FC {hex(app_fc)}")
                is_control = app_fc in (0x03, 0x04, 0x05, 0x06)  # Select, Operate, Direct Operate

                target_actuator = None
                target_value = None

                if is_control:
                    # Emulate parsing CROB / Analog Output
                    # e.g., Group 12 Var 1: Control Relay Output Block
                    target_actuator = 1  # e.g. ACT-01 Primary Pump
                    target_value = 1

                evt = self.logger.create_and_log(
                    protocol="DNP3",
                    source_ip=client_ip,
                    source_port=client_port,
                    dest_ip=self.host,
                    dest_port=self.port,
                    function_code=app_fc,
                    function_name=fc_name,
                    unit_id=1,
                    address=target_actuator,
                    value=target_value,
                    raw_payload_hex=full_frame.hex(),
                    is_anomaly=is_control,
                    anomaly_reason="Unauthorized DNP3 Direct Operate / CROB command injection" if is_control else None,
                    metadata={"dnp3_fc": hex(app_fc), "frame_len": len(full_frame)},
                )

                if is_control and self.twin_mirror_callback:
                    self.twin_mirror_callback({
                        "source": "DNP3",
                        "fc": app_fc,
                        "address": target_actuator,
                        "value": target_value,
                        "client_ip": client_ip,
                        "network_event_id": evt.event_id,
                    })

                # Build authentic DNP3 Null Response (Success / Echo)
                # Link header (10B) + Transport (1B: FIN|FIR|SEQ) + App Response (3B: Control, FC 0x81, IIN 0x00 0x00) + CRC
                resp_payload = bytes([
                    0xC0,        # Transport Header (FIN=1, FIR=1, SEQ=0)
                    0x80,        # App Control
                    0x81,        # Function Code: Response
                    0x00, 0x00   # Internal Indications (IIN: normal)
                ])
                resp_len = 5 + len(resp_payload)
                resp_hdr = struct.pack("<BBBBHH", 0x05, 0x64, resp_len, 0x44, 1, 1024)
                # Append placeholder CRC
                resp_frame = resp_hdr + b"\x00\x00" + resp_payload + b"\x00\x00"
                writer.write(resp_frame)
                await writer.drain()

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
