/**
 * 500+ Scenario Benchmark Runner & Scenario Explorer UI.
 */

class BenchmarkRunner {
  constructor() {
    this.btnRun = document.getElementById('btn-start-benchmark');
    this.progressBox = document.getElementById('benchmark-progress-box');
    this.progressBar = document.getElementById('benchmark-bar-fill');
    this.progressPct = document.getElementById('benchmark-progress-pct');
    this.progressText = document.getElementById('benchmark-progress-text');
    this.scenariosTable = document.getElementById('tbody-scenarios');

    this.initEvents();
    this.loadSampleScenarios();
  }

  initEvents() {
    if (this.btnRun) {
      this.btnRun.addEventListener('click', () => this.runBenchmark());
    }
  }

  async loadSampleScenarios() {
    if (!this.scenariosTable) return;
    try {
      const res = await fetch('/api/scenarios?count=15');
      const scenarios = await res.json();

      this.scenariosTable.innerHTML = scenarios.map(s => `
        <tr>
          <td><strong style="color: var(--accent-cyan);">${s.scenario_id}</strong></td>
          <td>${s.category}</td>
          <td><span class="tag-protocol">${s.protocol}</span></td>
          <td><code>${s.target_actuator}</code></td>
          <td><span class="mitre-pill">${s.mitre_id}</span></td>
          <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${s.description}">
            ${s.description}
          </td>
          <td><span class="badge-status normal">${s.complexity}</span></td>
          <td>
            <button class="act-btn" onclick="window.benchmarkRunner.runSingle('${s.scenario_id}')">
              ⚡ Launch
            </button>
          </td>
        </tr>
      `).join('');
    } catch (e) {
      console.error("Failed to load scenarios:", e);
    }
  }

  async runSingle(scenarioId) {
    try {
      const res = await fetch('/api/scenarios/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId }),
      });
      const data = await res.json();
      alert(`Attack Scenario ${scenarioId} executed!\n\n` +
            `MITRE ICS: ${data.scenario.mitre_id} (${data.scenario.mitre_name})\n` +
            `Safety Intervention: ${data.damage_prevented ? 'SUCCESS (Damage Prevented)' : 'Monitored'}\n` +
            `Reconstruction Match: ${data.reconstruction ? (data.reconstruction.is_overall_success ? 'MATCH (>=95% Acc)' : 'Partial') : 'N/A'}`);
    } catch (e) {
      alert("Error launching scenario: " + e);
    }
  }

  async runBenchmark() {
    if (this.btnRun) this.btnRun.disabled = true;
    if (this.progressBox) this.progressBox.style.display = 'block';

    // Simulate rapid progress animation
    let currentPct = 0;
    const interval = setInterval(() => {
      currentPct = Math.min(95, currentPct + Math.floor(Math.random() * 15) + 5);
      if (this.progressBar) this.progressBar.style.width = `${currentPct}%`;
      if (this.progressPct) this.progressPct.textContent = `${currentPct}%`;
      if (this.progressText) this.progressText.textContent = `Evaluating scenario batch (${Math.round((currentPct/100)*500)} / 500)...`;
    }, 40);

    try {
      const res = await fetch('/api/benchmark/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: 500, fast_mode: true }),
      });
      const summary = await res.json();

      clearInterval(interval);
      if (this.progressBar) this.progressBar.style.width = '100%';
      if (this.progressPct) this.progressPct.textContent = '100%';
      if (this.progressText) this.progressText.textContent = `Completed 500 scenarios in ${summary.elapsed_seconds}s!`;

      // Update UI Metric Cards
      const recon = summary.forensic_reconstruction;
      const safety = summary.safety_controller;

      document.getElementById('metric-total-scenarios').textContent = summary.total_scenarios_run;
      document.getElementById('metric-accuracy').textContent = `${recon.accuracy_pct}%`;
      document.getElementById('metric-precision-recall').textContent = `${recon.precision_pct}% / ${recon.recall_pct}%`;
      document.getElementById('metric-damage-prevented').textContent = `${safety.damage_prevented_rate_pct}%`;
      document.getElementById('metric-reaction-time').textContent = `${safety.mean_reaction_time_ms} ms`;

      // Update header badge
      const headerAcc = document.getElementById('recon-acc-text');
      if (headerAcc) headerAcc.textContent = `${recon.accuracy_pct}%`;

    } catch (e) {
      clearInterval(interval);
      alert("Benchmark failed: " + e);
    } finally {
      if (this.btnRun) this.btnRun.disabled = false;
    }
  }
}

window.BenchmarkRunner = BenchmarkRunner;
