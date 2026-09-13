/**
 * 12-Actuator Bank & Safety Interlock UI for CPH-TM.
 * Manages interactive actuator cards, sliders, isolation toggles, and status badges.
 */

class ActuatorsUI {
  constructor(containerId, onCommandCallback) {
    this.container = document.getElementById(containerId);
    this.onCommand = onCommandCallback || (() => {});
    this.actuatorData = {};
    this.renderedCards = {};
  }

  update(actuators) {
    if (!actuators) return;
    this.actuatorData = actuators;

    // Check if initial render is needed
    if (Object.keys(this.renderedCards).length === 0) {
      this.renderAll();
    } else {
      this.updateValues();
    }
  }

  renderAll() {
    if (!this.container) return;
    this.container.innerHTML = '';
    this.renderedCards = {};

    const ids = Object.keys(this.actuatorData).sort();
    ids.forEach(id => {
      const act = this.actuatorData[id];
      const card = document.createElement('div');
      card.className = `actuator-card ${act.is_isolated ? 'isolated' : ''}`;
      card.id = `card-${id}`;

      card.innerHTML = `
        <div class="act-card-header">
          <div>
            <span class="act-id-badge">${act.actuator_id}</span>
            <div class="act-name">${act.name}</div>
          </div>
          <span class="act-status-pill ${act.is_isolated ? 'isolated' : 'active'}" id="pill-${id}">
            ${act.is_isolated ? 'ISOLATED' : 'ACTIVE'}
          </span>
        </div>

        <div class="act-meter-group">
          <div>
            <span class="act-val" id="val-${id}">${Math.round(act.current_value)}</span>
            <span class="s-unit">${act.unit}</span>
          </div>
          <span class="act-power" id="pwr-${id}">${act.current_power_w} W</span>
        </div>

        <div class="progress-bar-bg">
          <div class="progress-fill" id="bar-${id}" style="width: ${(act.current_value / Math.max(1, act.max_value)) * 100}%;"></div>
        </div>

        <input type="range" class="act-slider" id="slider-${id}"
          min="${act.min_value}" max="${act.max_value}" step="1"
          value="${act.target_value}" ${act.is_isolated ? 'disabled' : ''}>

        <div class="act-actions">
          <button class="act-btn btn-trip" data-id="${id}" data-action="toggle-isolate" id="btn-iso-${id}">
            ${act.is_isolated ? 'RESTORE RELAY' : 'TRIP ISOLATE'}
          </button>
        </div>
      `;

      // Event listener for slider
      const slider = card.querySelector(`#slider-${id}`);
      slider.addEventListener('change', (e) => {
        this.onCommand('SET_ACTUATOR', { actuator_id: id, value: parseFloat(e.target.value) });
      });

      // Event listener for trip/restore button
      const btnIso = card.querySelector(`#btn-iso-${id}`);
      btnIso.addEventListener('click', () => {
        const isIso = this.actuatorData[id].is_isolated;
        this.onCommand(isIso ? 'RESTORE_ACTUATOR' : 'ISOLATE_ACTUATOR', { actuator_id: id });
      });

      this.container.appendChild(card);
      this.renderedCards[id] = card;
    });
  }

  updateValues() {
    Object.keys(this.actuatorData).forEach(id => {
      const act = this.actuatorData[id];
      const card = this.renderedCards[id];
      if (!card) return;

      if (act.is_isolated) {
        card.classList.add('isolated');
      } else {
        card.classList.remove('isolated');
      }

      const pill = card.querySelector(`#pill-${id}`);
      if (pill) {
        pill.className = `act-status-pill ${act.is_isolated ? 'isolated' : 'active'}`;
        pill.textContent = act.is_isolated ? 'ISOLATED' : 'ACTIVE';
      }

      const valEl = card.querySelector(`#val-${id}`);
      if (valEl) valEl.textContent = Math.round(act.current_value);

      const pwrEl = card.querySelector(`#pwr-${id}`);
      if (pwrEl) pwrEl.textContent = `${act.current_power_w} W`;

      const bar = card.querySelector(`#bar-${id}`);
      if (bar) {
        const pct = (act.current_value / Math.max(1, act.max_value)) * 100;
        bar.style.width = `${Math.max(0, Math.min(100, pct))}%`;
      }

      const slider = card.querySelector(`#slider-${id}`);
      if (slider && document.activeElement !== slider) {
        slider.value = act.target_value;
        slider.disabled = act.is_isolated;
      }

      const btnIso = card.querySelector(`#btn-iso-${id}`);
      if (btnIso) {
        btnIso.textContent = act.is_isolated ? 'RESTORE RELAY' : 'TRIP ISOLATE';
      }
    });
  }
}

window.ActuatorsUI = ActuatorsUI;
