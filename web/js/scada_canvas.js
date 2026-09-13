/**
 * SCADA P&ID Canvas Renderer for CPH-TM Live Digital Twin.
 * Renders real-time industrial hydro-chemical process with animated pipes,
 * liquid tanks, rotating pump impellers, agitators, and pressure relief valves.
 */

class ScadaCanvas {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    
    // Animation state
    this.flowOffset = 0;
    this.impellerAngle = 0;
    this.agitatorAngle = 0;
    this.wavePhase = 0;

    // Physical telemetry cache
    this.telemetry = {
      tank_level_pct: 62.5,
      reactor_level_pct: 58.0,
      reactor_pressure_psi: 48.5,
      reactor_temp_c: 64.2,
      vibration_mms: 1.2,
      cavitation_index: 0.0,
      inflow_rate_lpm: 120.0,
      outflow_rate_lpm: 118.0,
      is_overpressure_critical: false,
      is_thermal_runaway: false,
      is_resonance_lock: false,
    };

    this.actuators = {};
    this.isTripped = false;

    // Start render loop
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  updateData(telemetry, actuators, isTripped) {
    if (telemetry) this.telemetry = { ...this.telemetry, ...telemetry };
    if (actuators) this.actuators = actuators;
    this.isTripped = !!isTripped;
  }

  animate() {
    this.render();
    // Advance physics animation offsets
    const flowSpeed = Math.max(0.5, (this.telemetry.inflow_rate_lpm / 100.0) * 2.0);
    this.flowOffset = (this.flowOffset + flowSpeed) % 20;

    const pumpRpm = this.actuators['ACT-01'] ? this.actuators['ACT-01'].current_value : 1800;
    this.impellerAngle += (pumpRpm / 3600.0) * 0.25;

    const agitatorRpm = this.actuators['ACT-05'] ? this.actuators['ACT-05'].current_value : 1200;
    this.agitatorAngle += (agitatorRpm / 1800.0) * 0.3;

    this.wavePhase += 0.05;

    requestAnimationFrame(this.animate);
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // 1. Clear background
    ctx.fillStyle = '#060910';
    ctx.fillRect(0, 0, w, h);

    // Draw subtle engineering grid
    ctx.strokeStyle = 'rgba(52, 75, 115, 0.15)';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // 2. Draw Pipes & Piping Flow Paths
    this.drawPiping(ctx);

    // 3. Draw Vessels (Surge Tank 1 & Pressurized Reactor 2)
    this.drawSurgeTank(ctx, 120, 140, 160, 240);
    this.drawReactorVessel(ctx, 520, 110, 220, 280);

    // 4. Draw Mechanical Actuators & Valves
    this.drawPump(ctx, 330, 340, 'ACT-01', 'Primary Feed');
    this.drawValve(ctx, 420, 340, 'ACT-02', 'Inflow Vlv', false);
    this.drawAgitator(ctx, 630, 90, 'ACT-05');
    this.drawHeaterJacket(ctx, 510, 220, 240, 170, 'ACT-06');
    this.drawCoolingLoop(ctx, 750, 260, 'ACT-07');
    this.drawReliefValve(ctx, 630, 70, 'ACT-10', 'Relief Vlv');
    this.drawPump(ctx, 840, 340, 'ACT-08', 'Transfer Pump');

    // 5. Overall System Status Banner if Tripped
    if (this.isTripped) {
      ctx.fillStyle = 'rgba(255, 51, 102, 0.2)';
      ctx.fillRect(0, 0, w, 32);
      ctx.strokeStyle = '#ff3366';
      ctx.strokeRect(0, 0, w, 32);

      ctx.fillStyle = '#ff3366';
      ctx.font = 'bold 12px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText('⚠ SAFETY CONTROLLER INTERVENTION ACTIVE: ACTUATORS ISOLATED TO FAIL-SAFE CLAMP', w / 2, 21);
    }
  }

  drawPiping(ctx) {
    // Pipe 1: Intake to Tank 1
    this.renderPipe(ctx, [[40, 200], [120, 200]]);
    // Pipe 2: Tank 1 to Feed Pump ACT-01
    this.renderPipe(ctx, [[200, 380], [200, 420], [330, 420], [330, 350]]);
    // Pipe 3: Feed Pump to Reactor
    this.renderPipe(ctx, [[350, 340], [520, 340]]);
    // Pipe 4: Reactor discharge to Secondary Pump ACT-08
    this.renderPipe(ctx, [[740, 340], [840, 340]]);
    // Pipe 5: Reactor Relief Stack
    this.renderPipe(ctx, [[630, 110], [630, 50], [700, 50]], true);
  }

  renderPipe(ctx, points, isGas = false) {
    if (points.length < 2) return;

    // Outer pipe casing
    ctx.lineWidth = 14;
    ctx.strokeStyle = isGas ? '#2a3a55' : '#1a273f';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i][0], points[i][1]);
    }
    ctx.stroke();

    // Inner pipe fluid
    ctx.lineWidth = 8;
    ctx.strokeStyle = isGas ? 'rgba(0, 240, 255, 0.4)' : 'rgba(0, 150, 255, 0.6)';
    ctx.stroke();

    // Animated dashed flow particles
    ctx.lineWidth = 3;
    ctx.setLineDash([6, 12]);
    ctx.lineDashOffset = -this.flowOffset;
    ctx.strokeStyle = isGas ? '#00f0ff' : '#00ffff';
    ctx.stroke();
    ctx.setLineDash([]);
  }

  drawSurgeTank(ctx, x, y, w, h) {
    const level = Math.max(0, Math.min(100, this.telemetry.tank_level_pct)) / 100.0;
    const liquidH = (h - 20) * level;

    // Tank outline
    ctx.strokeStyle = '#344b73';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);

    // Liquid fill
    const liquidY = y + h - liquidH;
    const grad = ctx.createLinearGradient(x, liquidY, x, y + h);
    grad.addColorStop(0, 'rgba(0, 180, 255, 0.7)');
    grad.addColorStop(1, 'rgba(0, 80, 200, 0.85)');
    ctx.fillStyle = grad;
    ctx.fillRect(x + 2, liquidY, w - 4, liquidH);

    // Wave on top
    ctx.fillStyle = 'rgba(100, 220, 255, 0.5)';
    ctx.beginPath();
    ctx.moveTo(x + 2, liquidY);
    for (let px = x + 2; px <= x + w - 2; px += 10) {
      const wave = Math.sin((px + this.wavePhase * 20) * 0.08) * 3;
      ctx.lineTo(px, liquidY + wave);
    }
    ctx.lineTo(x + w - 2, liquidY + 5);
    ctx.lineTo(x + 2, liquidY + 5);
    ctx.fill();

    // Tank labels & Level text
    ctx.fillStyle = '#94a3b8';
    ctx.font = 'bold 11px "Outfit", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('SURGE TANK TK-01', x + w / 2, y - 10);

    ctx.fillStyle = '#fff';
    ctx.font = 'bold 14px "JetBrains Mono", monospace';
    ctx.fillText(`${(level * 100).toFixed(1)}%`, x + w / 2, y + h / 2);
  }

  drawReactorVessel(ctx, x, y, w, h) {
    const temp = this.telemetry.reactor_temp_c;
    const press = this.telemetry.reactor_pressure_psi;
    const level = Math.max(0, Math.min(100, this.telemetry.reactor_level_pct)) / 100.0;

    // Thermal color modulation
    let vesselGlow = 'rgba(0, 240, 255, 0.1)';
    let vesselStroke = '#344b73';
    if (temp >= 85 || this.telemetry.is_thermal_runaway) {
      vesselGlow = 'rgba(255, 51, 102, 0.35)';
      vesselStroke = '#ff3366';
    } else if (temp >= 75) {
      vesselGlow = 'rgba(255, 170, 0, 0.25)';
      vesselStroke = '#ffaa00';
    }

    // Outer vessel pressure casing (dome top)
    ctx.save();
    ctx.fillStyle = vesselGlow;
    ctx.strokeStyle = vesselStroke;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(x + w / 2, y + 25, w / 2, 25, 0, Math.PI, 0);
    ctx.lineTo(x + w, y + h - 25);
    ctx.ellipse(x + w / 2, y + h - 25, w / 2, 25, 0, 0, Math.PI);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // Liquid fill inside reactor
    const liquidH = (h - 60) * level;
    const liquidY = y + h - 25 - liquidH;
    const grad = ctx.createLinearGradient(x, liquidY, x, y + h);
    if (temp > 80) {
      grad.addColorStop(0, 'rgba(255, 80, 80, 0.8)');
      grad.addColorStop(1, 'rgba(180, 20, 20, 0.9)');
    } else {
      grad.addColorStop(0, 'rgba(0, 240, 255, 0.7)');
      grad.addColorStop(1, 'rgba(0, 100, 220, 0.85)');
    }
    ctx.fillStyle = grad;
    ctx.fillRect(x + 6, liquidY, w - 12, liquidH);

    // Process labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = 'bold 12px "Outfit", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('CHEMICAL REACTOR RX-01', x + w / 2, y - 18);

    // Pressure & Temp Telemetry Callout inside Vessel
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 13px "JetBrains Mono", monospace';
    ctx.fillText(`${press.toFixed(1)} PSI`, x + w / 2, y + 90);
    ctx.font = 'bold 12px "JetBrains Mono", monospace';
    ctx.fillStyle = temp >= 80 ? '#ff3366' : (temp >= 72 ? '#ffaa00' : '#00f0ff');
    ctx.fillText(`${temp.toFixed(1)} °C`, x + w / 2, y + 110);
  }

  drawPump(ctx, x, y, id, name) {
    const act = this.actuators[id];
    const isIsolated = act ? act.is_isolated : false;
    const val = act ? act.current_value : 1800;

    // Pump outer circular casing
    ctx.beginPath();
    ctx.arc(x, y, 22, 0, Math.PI * 2);
    ctx.fillStyle = isIsolated ? 'rgba(255, 51, 102, 0.2)' : 'rgba(20, 30, 50, 0.9)';
    ctx.strokeStyle = isIsolated ? '#ff3366' : (val > 0 ? '#00ff9d' : '#64748b');
    ctx.lineWidth = 2.5;
    ctx.fill();
    ctx.stroke();

    // Rotating impeller blades
    ctx.save();
    ctx.translate(x, y);
    if (!isIsolated && val > 0) {
      ctx.rotate(this.impellerAngle);
    }
    ctx.strokeStyle = isIsolated ? '#ff3366' : '#00f0ff';
    ctx.lineWidth = 2;
    for (let i = 0; i < 4; i++) {
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(14, 0);
      ctx.stroke();
      ctx.rotate(Math.PI / 2);
    }
    ctx.restore();

    // Label
    ctx.fillStyle = '#94a3b8';
    ctx.font = 'bold 10px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(id, x, y + 36);
    ctx.fillStyle = isIsolated ? '#ff3366' : '#fff';
    ctx.fillText(`${Math.round(val)} RPM`, x, y + 48);
  }

  drawValve(ctx, x, y, id, name, isVertical = false) {
    const act = this.actuators[id];
    const isIsolated = act ? act.is_isolated : false;
    const val = act ? act.current_value : 50;

    ctx.save();
    ctx.translate(x, y);
    if (isVertical) ctx.rotate(Math.PI / 2);

    // Two opposing triangles (standard P&ID valve symbol)
    ctx.fillStyle = isIsolated ? '#ff3366' : (val > 0 ? '#00f0ff' : '#64748b');
    ctx.beginPath();
    ctx.moveTo(-12, -10);
    ctx.lineTo(0, 0);
    ctx.lineTo(-12, 10);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(12, -10);
    ctx.lineTo(0, 0);
    ctx.lineTo(12, 10);
    ctx.closePath();
    ctx.fill();

    // Valve stem
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -14);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, -16, 4, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();

    ctx.fillStyle = '#94a3b8';
    ctx.font = 'bold 10px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(id, x, y + 24);
    ctx.fillStyle = isIsolated ? '#ff3366' : '#fff';
    ctx.fillText(`${Math.round(val)}%`, x, y + 36);
  }

  drawAgitator(ctx, x, y, id) {
    const act = this.actuators[id];
    const isIsolated = act ? act.is_isolated : false;
    const val = act ? act.current_value : 1200;
    const isResonance = this.telemetry.is_resonance_lock;

    // Agitator motor housing
    ctx.fillStyle = isResonance ? '#ffaa00' : (isIsolated ? '#ff3366' : '#1e293b');
    ctx.strokeStyle = isIsolated ? '#ff3366' : '#38bdf8';
    ctx.lineWidth = 2;
    ctx.fillRect(x - 18, y - 30, 36, 30);
    ctx.strokeRect(x - 18, y - 30, 36, 30);

    // Agitator shaft down into reactor
    ctx.strokeStyle = '#cbd5e1';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x, y + 200);
    ctx.stroke();

    // Spinning impeller paddles at bottom
    ctx.save();
    ctx.translate(x, y + 200);
    if (!isIsolated && val > 0) {
      ctx.rotate(this.agitatorAngle);
    }
    ctx.fillStyle = isResonance ? '#ffaa00' : '#38bdf8';
    ctx.fillRect(-35, -5, 70, 10);
    ctx.restore();

    ctx.fillStyle = '#94a3b8';
    ctx.font = 'bold 10px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${id} AGITATOR`, x, y - 36);
  }

  drawHeaterJacket(ctx, x, y, w, h, id) {
    const act = this.actuators[id];
    const val = act ? act.current_value : 5.0;
    const isIsolated = act ? act.is_isolated : false;

    if (val > 0 && !isIsolated) {
      ctx.strokeStyle = 'rgba(255, 100, 50, 0.4)';
      ctx.lineWidth = 4;
      ctx.setLineDash([8, 8]);
      ctx.strokeRect(x - 4, y, w + 8, h);
      ctx.setLineDash([]);
    }
  }

  drawCoolingLoop(ctx, x, y, id) {
    this.drawValve(ctx, x, y, id, 'Cooling', false);
  }

  drawReliefValve(ctx, x, y, id, name) {
    const act = this.actuators[id];
    const isOpen = act && act.current_value > 50;

    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = isOpen ? '#ff3366' : '#64748b';
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#fff';
    ctx.font = 'bold 9px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText(isOpen ? 'VENT' : 'PSV', 0, 3);
    ctx.restore();
  }
}

window.ScadaCanvas = ScadaCanvas;
