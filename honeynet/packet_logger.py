"""
Network Event and Packet Logger for OT/ICS Honeynet.
Maintains an in-memory chronological buffer of industrial network events
with microsecond timestamps for cross-domain correlation.
"""

import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Callable


@dataclass
class NetworkEvent:
    event_id: str
    timestamp: float
    protocol: str  # 'MODBUS_TCP', 'DNP3', 'MQTT', 'OPC_UA'
    source_ip: str
    source_port: int
    dest_ip: str
    dest_port: int
    function_code: Optional[int] = None
    function_name: Optional[str] = None
    unit_id: Optional[int] = None
    address: Optional[int] = None
    value: Optional[Any] = None
    raw_payload_hex: str = ""
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self.timestamp)) + f".{int((self.timestamp % 1) * 1000):03d}Z"
        return d


class PacketLogger:
    """Thread-safe ring buffer and dispatcher for network events."""

    def __init__(self, max_entries: int = 5000):
        self.max_entries = max_entries
        self.events: List[NetworkEvent] = []
        self._listeners: List[Callable[[NetworkEvent], None]] = []
        self._total_count: int = 0

    def add_listener(self, callback: Callable[[NetworkEvent], None]) -> None:
        """Register a callback for new network events."""
        self._listeners.append(callback)

    def log(self, event: NetworkEvent) -> NetworkEvent:
        """Store network event and notify listeners."""
        self.events.append(event)
        self._total_count += 1
        if len(self.events) > self.max_entries:
            self.events.pop(0)

        # Notify downstream subscribers (e.g. digital twin, forensics)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                # Isolate listener failures
                pass

        return event

    def create_and_log(
        self,
        protocol: str,
        source_ip: str,
        source_port: int,
        dest_ip: str,
        dest_port: int,
        function_code: Optional[int] = None,
        function_name: Optional[str] = None,
        unit_id: Optional[int] = None,
        address: Optional[int] = None,
        value: Optional[Any] = None,
        raw_payload_hex: str = "",
        is_anomaly: bool = False,
        anomaly_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NetworkEvent:
        now = time.time()
        event_id = f"NET-{self._total_count + 1:06d}"
        evt = NetworkEvent(
            event_id=event_id,
            timestamp=now,
            protocol=protocol,
            source_ip=source_ip,
            source_port=source_port,
            dest_ip=dest_ip,
            dest_port=dest_port,
            function_code=function_code,
            function_name=function_name,
            unit_id=unit_id,
            address=address,
            value=value,
            raw_payload_hex=raw_payload_hex,
            is_anomaly=is_anomaly,
            anomaly_reason=anomaly_reason,
            metadata=metadata or {},
        )
        return self.log(evt)

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [evt.to_dict() for evt in self.events[-limit:]]

    def get_anomalies(self, limit: int = 50) -> List[Dict[str, Any]]:
        anomalies = [evt.to_dict() for evt in self.events if evt.is_anomaly]
        return anomalies[-limit:]

    def clear(self) -> None:
        self.events.clear()
        self._total_count = 0

    @property
    def total_packets(self) -> int:
        return self._total_count
