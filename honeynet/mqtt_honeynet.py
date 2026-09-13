"""
Lightweight Asynchronous MQTT / IIoT Honeynet Listener.
Emulates an industrial SCADA / Sparkplug edge broker on port 1883.
Captures adversarial MQTT publish payloads directed at industrial control topics.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Callable
from .packet_logger import PacketLogger

class MQTTHoneynetServer:
    """Async MQTT honeypot listener."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 1883,
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
                # Read fixed header: Byte 1 = Packet type & flags, Byte 2..5 = Remaining length
                first_byte = await reader.read(1)
                if not first_byte:
                    break

                pkt_type = (first_byte[0] >> 4) & 0x0F
                # Read remaining length (variable length encoding)
                rem_len = 0
                multiplier = 1
                while True:
                    b = await reader.read(1)
                    if not b:
                        break
                    digit = b[0]
                    rem_len += (digit & 127) * multiplier
                    multiplier *= 128
                    if (digit & 128) == 0:
                        break

                payload = await reader.read(rem_len) if rem_len > 0 else b""
                raw_hex = (first_byte + payload).hex()

                # Packet Type 1: CONNECT
                if pkt_type == 1:
                    # Respond with CONNACK (0x20, length 2, flags 0, return code 0: accepted)
                    writer.write(bytes([0x20, 0x02, 0x00, 0x00]))
                    await writer.drain()

                # Packet Type 3: PUBLISH
                elif pkt_type == 3:
                    # Decode topic name
                    topic_len = (payload[0] << 8) | payload[1]
                    topic = payload[2 : 2 + topic_len].decode("utf-8", errors="replace")
                    msg_body = payload[2 + topic_len :].decode("utf-8", errors="replace")

                    is_override = "override" in topic or "setpoint" in topic or "emergency" in topic
                    evt = self.logger.create_and_log(
                        protocol="MQTT",
                        source_ip=client_ip,
                        source_port=client_port,
                        dest_ip=self.host,
                        dest_port=self.port,
                        function_name="PUBLISH",
                        address=None,
                        value=msg_body,
                        raw_payload_hex=raw_hex,
                        is_anomaly=is_override,
                        anomaly_reason=f"Adversarial MQTT publish to industrial topic: {topic}" if is_override else None,
                        metadata={"topic": topic, "payload": msg_body},
                    )

                    if self.twin_mirror_callback:
                        self.twin_mirror_callback({
                            "source": "MQTT",
                            "topic": topic,
                            "value": msg_body,
                            "client_ip": client_ip,
                            "network_event_id": evt.event_id,
                        })

                    # If QoS 1, send PUBACK
                    qos = (first_byte[0] >> 1) & 0x03
                    if qos == 1 and len(payload) >= 2 + topic_len + 2:
                        pkt_id = payload[2 + topic_len : 4 + topic_len]
                        writer.write(bytes([0x40, 0x02]) + pkt_id)
                        await writer.drain()

                # Packet Type 8: SUBSCRIBE
                elif pkt_type == 8:
                    # Send SUBACK (0x90, len 3, packet_id 2B, return code 0)
                    pkt_id = payload[0:2] if len(payload) >= 2 else b"\x00\x01"
                    writer.write(bytes([0x90, 0x03]) + pkt_id + bytes([0x00]))
                    await writer.drain()

                # Packet Type 12: PINGREQ
                elif pkt_type == 12:
                    writer.write(bytes([0xD0, 0x00]))
                    await writer.drain()

                # Packet Type 14: DISCONNECT
                elif pkt_type == 14:
                    break

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
