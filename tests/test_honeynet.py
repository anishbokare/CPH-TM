"""
Unit tests for OT/ICS Honeynet components (Modbus TCP, DNP3, PacketLogger).
"""

import pytest
import asyncio
import struct
from honeynet.packet_logger import PacketLogger, NetworkEvent
from honeynet.modbus_honeynet import ModbusHoneynetServer
from honeynet.dnp3_honeynet import DNP3HoneynetServer


def test_packet_logger():
    logger = PacketLogger(max_entries=10)
    for i in range(15):
        logger.create_and_log(
            protocol="MODBUS_TCP",
            source_ip="192.168.1.50",
            source_port=50000 + i,
            dest_ip="127.0.0.1",
            dest_port=1502,
            function_code=6,
            address=i,
            value=100 + i,
            is_anomaly=(i % 2 == 0),
        )

    assert logger.total_packets == 15
    assert len(logger.events) == 10  # Enforces max_entries ring buffer
    anomalies = logger.get_anomalies(limit=50)
    assert len(anomalies) > 0


@pytest.mark.asyncio
async def test_modbus_pdu_processing():
    mirrored_commands = []

    def callback(cmd):
        mirrored_commands.append(cmd)

    logger = PacketLogger()
    server = ModbusHoneynetServer(logger=logger, twin_mirror_callback=callback)

    # Test FC3: Read Holding Registers (start 0, count 2)
    pdu_read = bytes([0x03, 0x00, 0x00, 0x00, 0x02])
    resp, info = server._process_pdu(pdu_read, unit_id=1, client_ip="127.0.0.1", client_port=51000)
    assert resp[0] == 0x03
    assert resp[1] == 4  # 2 registers * 2 bytes = 4 bytes

    # Test FC6: Write Single Register (addr 0 = 950 PSI -> should flag anomaly)
    pdu_write = bytes([0x06, 0x00, 0x00, 0x03, 0xB6])
    resp_w, info_w = server._process_pdu(pdu_write, unit_id=1, client_ip="10.0.0.1", client_port=51001)
    assert resp_w[0] == 0x06
    assert info_w["is_write"] is True
    assert info_w["is_anomaly"] is True
    assert server.holding_registers[0] == 950

    # Test FC43: Device Identification
    pdu_id = bytes([0x2B, 0x0E, 0x01, 0x00])
    resp_id, info_id = server._process_pdu(pdu_id, unit_id=1, client_ip="10.0.0.1", client_port=51002)
    assert b"Schneider Electric" in resp_id


@pytest.mark.asyncio
async def test_dnp3_server_initialization():
    logger = PacketLogger()
    dnp3 = DNP3HoneynetServer(logger=logger)
    assert dnp3.port == 20000
    assert not dnp3.is_running
