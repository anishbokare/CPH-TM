"""
FastAPI Server & Cyber-Physical Orchestration Engine for CPH-TM.
Ties together OT Honeypots, Live Digital Twin Simulation, Safety Controller,
Forensic Correlation Pipeline, and WebSocket Real-Time Broadcast.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from honeynet.packet_logger import PacketLogger
from honeynet.modbus_honeynet import ModbusHoneynetServer
from honeynet.dnp3_honeynet import DNP3HoneynetServer
from honeynet.mqtt_honeynet import MQTTHoneynetServer

from digital_twin.actuators import ActuatorBank
from digital_twin.process_model import ProcessDigitalTwin
from digital_twin.rpi_gpio import HardwareInterface

from safety_controller.interlock_engine import SafetyController
from safety_controller.isolation_matrix import ActuatorIsolationMatrix

from forensics.correlator import ForensicCorrelator
from simulation.scenario_runner import ScenarioOrchestrator

from backend.api_routes import router as api_router, PLATFORM_CONTEXT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CPH-TM.Server")

# Global instances
logger_instance = PacketLogger()
hardware_hal = HardwareInterface()
actuator_bank = ActuatorBank()
twin = ProcessDigitalTwin(actuator_bank=actuator_bank, hardware=hardware_hal)
isolation_matrix = ActuatorIsolationMatrix()
safety = SafetyController(actuator_bank=actuator_bank, isolation_matrix=isolation_matrix, hardware=hardware_hal)
correlator = ForensicCorrelator()
orchestrator = ScenarioOrchestrator(logger=logger_instance, twin=twin, safety=safety, correlator=correlator)

# Wire callbacks
logger_instance.add_listener(correlator.on_network_event)
safety.add_listener(lambda trip: correlator.on_safety_trip(trip, twin.state))

# Honeynet servers
modbus_server = ModbusHoneynetServer(
    host="0.0.0.0",
    port=1502,
    logger=logger_instance,
    twin_mirror_callback=twin.mirror_network_write,
)
dnp3_server = DNP3HoneynetServer(
    host="0.0.0.0",
    port=20000,
    logger=logger_instance,
    twin_mirror_callback=twin.mirror_network_write,
)
mqtt_server = MQTTHoneynetServer(
    host="0.0.0.0",
    port=1883,
    logger=logger_instance,
    twin_mirror_callback=twin.mirror_network_write,
)

# Populate API context
PLATFORM_CONTEXT.update({
    "logger": logger_instance,
    "twin": twin,
    "safety": safety,
    "correlator": correlator,
    "orchestrator": orchestrator,
})


class ConnectionManager:
    """Manages real-time WebSocket clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        data = json.dumps(message)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)


ws_manager = ConnectionManager()
sim_task = None
honeynet_tasks = []


async def digital_twin_loop():
    """Real-time physics and safety interlock loop executing at 20 Hz."""
    logger.info("Starting live digital twin physics and safety evaluation loop (20 Hz)...")
    last_broadcast = 0.0

    while True:
        try:
            # 1. Step physical simulation
            twin.step(dt=0.05)

            # 2. Evaluate safety interlocks
            safety.evaluate(twin.state)

            # 3. Broadcast telemetry via WebSocket at ~15 Hz
            now = asyncio.get_event_loop().time()
            if now - last_broadcast >= 0.065:
                last_broadcast = now
                packet = {
                    "type": "TELEMETRY_UPDATE",
                    "physical_state": twin.state.to_dict(),
                    "actuators": twin.actuators.get_states(),
                    "isolation": safety.isolation.get_summary(),
                    "hardware": twin.hardware.get_hardware_state(),
                    "recent_packets": logger_instance.get_recent(5),
                    "recent_incidents": correlator.get_recent_incidents(5),
                    "total_packets": logger_instance.total_packets,
                }
                await ws_manager.broadcast(packet)

            await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in digital twin loop: {e}", exc_info=True)
            await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sim_task, honeynet_tasks
    logger.info("Initializing CPH-TM Cyber-Physical Platform...")

    # Start honeynet listener tasks
    try:
        await modbus_server.start()
        logger.info("Modbus TCP Honeynet active on 0.0.0.0:1502")
    except Exception as e:
        logger.warning(f"Could not bind Modbus TCP port 1502: {e}")

    try:
        await dnp3_server.start()
        logger.info("DNP3 Outstation Honeynet active on 0.0.0.0:20000")
    except Exception as e:
        logger.warning(f"Could not bind DNP3 port 20000: {e}")

    try:
        await mqtt_server.start()
        logger.info("MQTT Honeynet Broker active on 0.0.0.0:1883")
    except Exception as e:
        logger.warning(f"Could not bind MQTT port 1883: {e}")

    # Start digital twin physics simulation loop
    sim_task = asyncio.create_task(digital_twin_loop())

    yield

    logger.info("Shutting down CPH-TM Platform...")
    if sim_task:
        sim_task.cancel()
        try:
            await sim_task
        except asyncio.CancelledError:
            pass

    await modbus_server.stop()
    await dnp3_server.stop()
    await mqtt_server.stop()
    hardware_hal.cleanup()


app = FastAPI(
    title="Cyber-Physical Honeynet with Live Digital Twin Mirroring",
    description="Industrial OT/ICS Honeynet paired with Live Digital Twin and Safety Controller",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Handle incoming commands from dashboard via WebSocket
            data = await websocket.receive_text()
            cmd = json.loads(data)
            action = cmd.get("action")
            if action == "SET_ACTUATOR":
                twin.actuators.set_target(cmd["actuator_id"], cmd["value"])
            elif action == "ISOLATE_ACTUATOR":
                safety.isolation.trip_actuator(cmd["actuator_id"], "User command")
                twin.actuators.isolate(cmd["actuator_id"])
            elif action == "RESTORE_ACTUATOR":
                safety.isolation.restore_actuator(cmd["actuator_id"])
                twin.actuators.restore(cmd["actuator_id"])
            elif action == "ESTOP":
                safety.manual_estop()
            elif action == "RESET":
                safety.reset_safety()
                twin.reset_process()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# Mount static web UI
web_dir = Path(__file__).resolve().parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(web_dir / "index.html"))
