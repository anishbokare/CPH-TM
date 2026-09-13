/**
 * Main Client Controller for CPH-TM Industrial SCADA Dashboard.
 * Connects WebSocket telemetry stream, manages tabs, attack injections, and audits.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Subcomponents
  const scadaCanvas = new ScadaCanvas('scada-canvas');
  const actuatorsUI = new ActuatorsUI('actuators-card-grid', sendWebSocketCommand);
  const forensicTimeline = new ForensicTimeline('forensic-timeline-list', 'mitre-badges-list');
  window.benchmarkRunner = new BenchmarkRunner();

  let ws = null;
  let packetCache = [];
  let currentFilter = 'all';

  // 2. Setup WebSocket Connection
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[CPH-TM] WebSocket connection established.");
      const dot = document.getElementById('sys-status-dot');
      if (dot) dot.className = 'indicator-dot green';
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'TELEMETRY_UPDATE') {
          handleTelemetryUpdate(msg);
        }
      } catch (e) {
        console.error("WS Parse error:", e);
      }
    };

    ws.onclose = () => {
      console.warn("[CPH-TM] WebSocket closed. Reconnecting in 2s...");
      const dot = document.getElementById('sys-status-dot');
      if (dot) dot.className = 'indicator-dot red';
      setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = (err) => {
      console.error("[CPH-TM] WebSocket error:", err);
      ws.close();
    };
  }

  function sendWebSocketCommand(action, payload = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action, ...payload }));
    } else {
      // Fallback to REST API
      if (action === 'SET_ACTUATOR') {
        fetch(`/api/actuators/${payload.actuator_id}/set`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value: payload.value }),
        });
      } else if (action === 'ISOLATE_ACTUATOR') {
        fetch(`/api/actuators/${payload.actuator_id}/isolate`, { method: 'POST' });
      } else if (action === 'RESTORE_ACTUATOR') {
        fetch(`/api/actuators/${payload.actuator_id}/restore`, { method: 'POST' });
      } else if (action === 'ESTOP') {
        fetch('/api/safety/estop', { method: 'POST' });
      } else if (action === 'RESET') {
        fetch('/api/safety/reset', { method: 'POST' });
      }
    }
  }

  // 3. Handle Telemetry Messages
  function handleTelemetryUpdate(data) {
    const phys = data.physical_state || {};
    const acts = data.actuators || {};
    const iso = data.isolation || {};
    const hal = data.hardware || {};

    const isTripped = iso.is_system_tripped;

    // Update canvas
    scadaCanvas.updateData(phys, acts, isTripped);

    // Update actuator cards
    actuatorsUI.update(acts);

    // Update forensics timeline
    if (data.recent_incidents) {
      forensicTimeline.update(data.recent_incidents);
    }

    // Update packets table
    if (data.recent_packets) {
      updatePacketStream(data.recent_packets);
    }

    // Update HUD gauges
    if (phys.reactor_pressure_psi !== undefined) {
      document.getElementById('val-pressure').textContent = phys.reactor_pressure_psi.toFixed(1);
      document.getElementById('bar-pressure').style.width = `${Math.min(100, (phys.reactor_pressure_psi / 85.0) * 100)}%`;
    }
    if (phys.reactor_temp_c !== undefined) {
      document.getElementById('val-temp').textContent = phys.reactor_temp_c.toFixed(1);
      document.getElementById('bar-temp').style.width = `${Math.min(100, (phys.reactor_temp_c / 88.0) * 100)}%`;
    }
    if (phys.tank_level_pct !== undefined) {
      document.getElementById('val-tank').textContent = phys.tank_level_pct.toFixed(1);
      document.getElementById('bar-tank').style.width = `${Math.min(100, phys.tank_level_pct)}%`;
    }
    if (phys.vibration_mms !== undefined) {
      document.getElementById('val-vibration').textContent = phys.vibration_mms.toFixed(1);
      document.getElementById('bar-vibration').style.width = `${Math.min(100, (phys.vibration_mms / 10.0) * 100)}%`;
    }
    if (phys.cavitation_index !== undefined) {
      document.getElementById('val-cavitation').textContent = phys.cavitation_index.toFixed(2);
      document.getElementById('bar-cavitation').style.width = `${Math.min(100, phys.cavitation_index * 100)}%`;
    }
    if (phys.ph_level !== undefined) {
      document.getElementById('val-ph').textContent = phys.ph_level.toFixed(2);
      document.getElementById('bar-ph').style.width = `${Math.min(100, (phys.ph_level / 14.0) * 100)}%`;
    }

    // Update status badges
    const sysDot = document.getElementById('sys-status-dot');
    const sysText = document.getElementById('sys-status-text');
    if (isTripped) {
      sysDot.className = 'indicator-dot red';
      sysText.textContent = `TRIP (${iso.isolated_count} ISOLATED)`;
      document.getElementById('safety-status-text').textContent = `${12 - iso.isolated_count}/12 ACTIVE`;
      document.getElementById('safety-status-text').style.color = 'var(--accent-red)';
    } else {
      sysDot.className = 'indicator-dot green';
      sysText.textContent = 'NOMINAL';
      document.getElementById('safety-status-text').textContent = '12/12 ACTIVE';
      document.getElementById('safety-status-text').style.color = 'var(--accent-green)';
    }

    // Total packet badge
    if (data.total_packets !== undefined) {
      document.getElementById('packet-count-text').textContent = `${data.total_packets} PKTS`;
    }

    // HAL Status
    if (hal.is_physical_pi) {
      document.getElementById('hal-status-text').textContent = 'RPI NATIVE GPIO';
      document.getElementById('rpi-mode-badge').textContent = 'PHYSICAL GPIO';
    }
  }

  // 4. Packet Stream & Hex Inspection
  function updatePacketStream(packets) {
    const tbody = document.getElementById('tbody-packets');
    if (!tbody || !packets) return;

    packets.forEach(p => {
      if (!packetCache.some(cp => cp.event_id === p.event_id)) {
        packetCache.unshift(p);
        if (packetCache.length > 100) packetCache.pop();

        // Update alert ticker with latest packet
        const ticker = document.getElementById('ticker-msg');
        if (ticker) {
          ticker.textContent = `[${p.protocol}] ${p.function_name || 'WRITE'} from ${p.source_ip} (Unit ${p.unit_id || 1}): ${p.anomaly_reason || 'Normal Command'}`;
        }
      }
    });

    renderFilteredPackets();
  }

  function renderFilteredPackets() {
    const tbody = document.getElementById('tbody-packets');
    if (!tbody) return;

    const filtered = packetCache.filter(p => {
      if (currentFilter === 'all') return true;
      if (currentFilter === 'anomaly') return p.is_anomaly;
      return p.protocol === currentFilter;
    });

    tbody.innerHTML = filtered.slice(0, 30).map(p => `
      <tr onclick="inspectPacket('${p.event_id}')">
        <td><strong style="color: var(--accent-cyan);">${p.event_id}</strong></td>
        <td>${p.timestamp_iso ? p.timestamp_iso.split('T')[1] : 'NOW'}</td>
        <td><span class="tag-protocol">${p.protocol}</span></td>
        <td><code>${p.source_ip}</code></td>
        <td>${p.function_name || 'FC' + p.function_code}</td>
        <td>${p.address !== null ? 'Reg/Coil #' + p.address : '-'}</td>
        <td>${p.value !== null ? p.value : '-'}</td>
        <td>
          <span class="badge-status ${p.is_anomaly ? 'anomaly' : 'normal'}">
            ${p.is_anomaly ? 'ANOMALY' : 'OK'}
          </span>
        </td>
      </tr>
    `).join('');
  }

  window.inspectPacket = function(eventId) {
    const pkt = packetCache.find(p => p.event_id === eventId);
    const container = document.getElementById('inspector-content');
    if (!pkt || !container) return;

    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-subtle); padding-bottom: 6px;">
          <strong style="color: var(--accent-cyan);">${pkt.event_id}</strong>
          <span class="tag-protocol">${pkt.protocol}</span>
        </div>
        <div style="font-size: 11px; line-height: 1.6;">
          <div><strong>Timestamp:</strong> ${pkt.timestamp_iso}</div>
          <div><strong>Source Address:</strong> <code>${pkt.source_ip}:${pkt.source_port}</code></div>
          <div><strong>Destination:</strong> <code>${pkt.dest_ip}:${pkt.dest_port}</code></div>
          <div><strong>Function:</strong> ${pkt.function_name} (Code: ${pkt.function_code})</div>
          <div><strong>Target Mapped ID:</strong> ${pkt.address !== null ? pkt.address : 'N/A'}</div>
          <div><strong>Command Value:</strong> <code>${pkt.value}</code></div>
          <div><strong>Detection:</strong> <span style="color: ${pkt.is_anomaly ? 'var(--accent-red)' : 'var(--accent-green)'};">${pkt.anomaly_reason || 'Verified Fieldbus Command'}</span></div>
        </div>

        <div style="margin-top: 10px;">
          <strong style="font-size: 11px; color: var(--text-muted);">RAW PROTOCOL FRAME (HEX INSPECTOR):</strong>
          <div class="hex-dump-box">${formatHex(pkt.raw_payload_hex || '0001000000060106000003b6')}</div>
        </div>
      </div>
    `;
  };

  function formatHex(hexStr) {
    if (!hexStr) return '';
    let res = '';
    for (let i = 0; i < hexStr.length; i += 2) {
      res += hexStr.substr(i, 2).toUpperCase() + ' ';
      if ((i + 2) % 32 === 0) res += '\n';
      else if ((i + 2) % 16 === 0) res += '  ';
    }
    return res;
  }

  // 5. Navigation Tab Switching
  const tabs = document.querySelectorAll('.nav-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPanel = document.getElementById(tab.dataset.target);
      if (targetPanel) targetPanel.classList.add('active');
    });
  });

  // Filter pills
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilter = pill.dataset.filter;
      renderFilteredPackets();
    });
  });

  // 6. Global Header Action Buttons
  document.getElementById('btn-estop').addEventListener('click', () => {
    sendWebSocketCommand('ESTOP');
  });

  document.getElementById('btn-reset-sys').addEventListener('click', () => {
    sendWebSocketCommand('RESET');
  });

  document.getElementById('btn-isolate-all').addEventListener('click', () => {
    sendWebSocketCommand('ESTOP');
  });

  document.getElementById('btn-restore-all').addEventListener('click', () => {
    sendWebSocketCommand('RESET');
  });

  // Quick Attack Injectors
  document.querySelectorAll('.attack-quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.attack;
      injectAttack(type);
    });
  });

  async function injectAttack(type) {
    let payload = {};
    if (type === 'overpressure') {
      payload = { protocol: 'MODBUS_TCP', function_code: 6, address: 0, value: 950, source_ip: '192.168.1.105' };
    } else if (type === 'thermal') {
      payload = { protocol: 'MODBUS_TCP', function_code: 6, address: 1, value: 920, source_ip: '10.0.4.88' };
    } else if (type === 'stuxnet') {
      payload = { protocol: 'MODBUS_TCP', function_code: 6, address: 3, value: 1500, source_ip: '172.16.20.12' };
    } else if (type === 'cavitation') {
      payload = { protocol: 'MODBUS_TCP', function_code: 6, address: 5, value: 5, source_ip: '198.51.100.42' };
    } else if (type === 'dnp3_rogue') {
      payload = { protocol: 'DNP3', function_code: 5, address: 1, value: 1, source_ip: '203.0.113.19' };
    } else if (type === 'mqtt_spoof') {
      payload = { protocol: 'MQTT', function_code: 0, address: 0, value: 95.0, source_ip: '45.154.255.89' };
    }

    try {
      const res = await fetch('/api/honeynet/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      console.log("Injected attack payload:", data);
    } catch (e) {
      alert("Injection failed: " + e);
    }
  }

  // 7. Audit Report Modal
  const modal = document.getElementById('report-modal');
  document.getElementById('btn-export-report').addEventListener('click', async () => {
    try {
      const res = await fetch('/api/forensics/report');
      const data = await res.json();
      document.getElementById('report-json-content').textContent = JSON.stringify(data, null, 2);
      modal.style.display = 'flex';
    } catch (e) {
      alert("Failed to generate report: " + e);
    }
  });

  document.getElementById('btn-close-modal').addEventListener('click', () => {
    modal.style.display = 'none';
  });
  document.getElementById('btn-modal-done').addEventListener('click', () => {
    modal.style.display = 'none';
  });

  document.getElementById('btn-download-json').addEventListener('click', () => {
    const text = document.getElementById('report-json-content').textContent;
    const blob = new Blob([text], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cph_tm_forensic_report_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // Start WebSocket
  connectWebSocket();
});
