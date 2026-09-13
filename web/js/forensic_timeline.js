/**
 * Cross-Domain Forensic Correlation & MITRE ATT&CK for ICS UI Component.
 */

class ForensicTimeline {
  constructor(timelineId, mitreId) {
    this.timelineContainer = document.getElementById(timelineId);
    this.mitreContainer = document.getElementById(mitreId);
    this.renderedIncidentIds = new Set();
    this.initMitreCatalog();
  }

  initMitreCatalog() {
    if (!this.mitreContainer) return;
    const techniques = [
      { id: "T0855", name: "Unauthorized Command Message", tactic: "Impair Process Control", desc: "Adversary injects unauthorized Modbus or DNP3 operate commands to actuate valves and pumps." },
      { id: "T0836", name: "Modify Parameter", tactic: "Impair Process Control", desc: "Modification of critical safety setpoints, pressure limits, or thermal regulator registers." },
      { id: "T0879", name: "Damage to Property", tactic: "Impact", desc: "Driving physical process variables into destructive structural zones (overpressure, thermal runaway, resonance)." },
      { id: "T0880", name: "Loss of Safety", tactic: "Impact", desc: "Attempted disablement or bypass of safety instrumented interlock functions." },
      { id: "T0831", name: "Manipulation of Control", tactic: "Impair Process Control", desc: "High-frequency switching of valves and pumps inducing hydraulic cavitation and water hammer." },
      { id: "T0814", name: "Denial of Service", tactic: "Inhibit Response", desc: "Burst packet flooding on industrial fieldbus to starve legitimate telemetry." },
      { id: "T0853", name: "Manipulation of View", tactic: "Impair Process Control", desc: "False sensor data injection spoofing operator displays while physical process exceeds limits." },
    ];

    this.mitreContainer.innerHTML = techniques.map(t => `
      <div class="mitre-entry">
        <div class="mitre-entry-header">
          <span class="mitre-tech-id">${t.id}</span>
          <span class="mitre-pill">${t.tactic}</span>
        </div>
        <div class="mitre-tech-name">${t.name}</div>
        <div class="mitre-tech-desc">${t.desc}</div>
      </div>
    `).join('');
  }

  update(incidents) {
    if (!this.timelineContainer || !incidents || incidents.length === 0) return;

    incidents.forEach(inc => {
      if (this.renderedIncidentIds.has(inc.incident_id)) return;
      this.renderedIncidentIds.add(inc.incident_id);

      const card = document.createElement('div');
      card.className = `incident-card ${inc.safety_intervened ? 'critical' : ''}`;
      card.innerHTML = `
        <div class="incident-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="inc-id">${inc.incident_id}</span>
            <span class="mitre-pill">${inc.mitre_technique_id} // ${inc.mitre_technique_name}</span>
          </div>
          <span class="inc-time">${inc.timestamp_iso || 'JUST NOW'}</span>
        </div>

        <div class="inc-correlation-grid">
          <div class="inc-domain-box">
            <span class="domain-label">🌐 CYBER DOMAIN (NETWORK INJECTION)</span>
            <span class="domain-value"><strong>${inc.protocol}</strong> from <code>${inc.source_ip}</code></span>
            <span class="domain-value" style="color: var(--text-muted); font-size: 10px;">${inc.payload_summary}</span>
          </div>

          <div class="inc-domain-box">
            <span class="domain-label">⚛ PHYSICAL DOMAIN (PROCESS DIVERGENCE)</span>
            <span class="domain-value">${inc.deviation_description}</span>
            <span class="domain-value" style="color: var(--text-muted); font-size: 10px;">
              P: ${inc.peak_pressure_psi.toFixed(1)} PSI | T: ${inc.peak_temp_c.toFixed(1)} °C | Vib: ${inc.peak_vibration_mms.toFixed(1)} mm/s
            </span>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px; margin-top: 4px;">
          <span style="color: var(--accent-green); font-family: var(--font-mono);">
            🛡 SAFETY INTERVENTION: ${inc.reaction_time_ms} ms (${inc.damage_prevented})
          </span>
          <span style="color: var(--text-muted); font-family: var(--font-mono); font-size: 10px;">
            Causal Delay: +${inc.network_to_physical_delay_ms} ms
          </span>
        </div>
      `;

      this.timelineContainer.insertBefore(card, this.timelineContainer.firstChild);
    });

    const counter = document.getElementById('incident-counter-badge');
    if (counter) {
      counter.textContent = `${this.renderedIncidentIds.size} INCIDENTS CORRELATED`;
    }
  }
}

window.ForensicTimeline = ForensicTimeline;
