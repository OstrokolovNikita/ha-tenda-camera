class TendaCameraCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._streamUrl = null;
    this._ptzActive = false;
    this._render();
  }

  static getStubConfig(hass) {
    const tendaCameras = Object.values(hass.states || {}).filter(
      (state) =>
        state.entity_id.startsWith("camera.") &&
        state.attributes?.brand === "Tenda"
    );
    const entity =
      tendaCameras.find((state) => state.attributes?.stream_role === "sub") ||
      tendaCameras.find((state) => state.attributes?.stream_role === "main");
    return { entity: entity?.entity_id || "" };
  }

  setConfig(config) {
    if (!config?.entity) {
      throw new Error("Tenda Camera card requires a camera entity");
    }
    this._config = { ...config };
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 5;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          overflow: hidden;
          position: relative;
          background: var(--ha-card-background, var(--card-background-color));
        }
        .stage {
          position: relative;
          width: 100%;
          aspect-ratio: 16 / 9;
          background: #111;
          overflow: hidden;
        }
        img.stream {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
          user-select: none;
          -webkit-user-drag: none;
        }
        .title {
          position: absolute;
          left: 12px;
          top: 10px;
          z-index: 4;
          padding: 6px 10px;
          border-radius: 14px;
          color: white;
          background: rgba(0, 0, 0, 0.45);
          font-size: 14px;
          backdrop-filter: blur(5px);
        }
        .events {
          position: absolute;
          left: 12px;
          bottom: 12px;
          z-index: 4;
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
          max-width: 55%;
        }
        .event {
          display: none;
          align-items: center;
          gap: 5px;
          padding: 5px 9px;
          border-radius: 14px;
          color: white;
          background: rgba(0, 0, 0, 0.48);
          font-size: 12px;
          backdrop-filter: blur(5px);
        }
        .event.active {
          display: inline-flex;
          background: rgba(220, 55, 45, 0.82);
        }
        .joystick {
          --size: 44px;
          position: absolute;
          right: 12px;
          bottom: 12px;
          z-index: 5;
          width: calc(var(--size) * 3);
          height: calc(var(--size) * 3);
          display: grid;
          grid-template-columns: repeat(3, var(--size));
          grid-template-rows: repeat(3, var(--size));
          touch-action: none;
          user-select: none;
        }
        .ptz {
          width: 40px;
          height: 40px;
          align-self: center;
          justify-self: center;
          border: 0;
          border-radius: 50%;
          color: white;
          background: rgba(0, 0, 0, 0.52);
          display: grid;
          place-items: center;
          cursor: pointer;
          backdrop-filter: blur(5px);
          -webkit-tap-highlight-color: transparent;
        }
        .ptz:active {
          background: rgba(3, 169, 244, 0.85);
          transform: scale(0.94);
        }
        .ptz.up { grid-column: 2; grid-row: 1; }
        .ptz.left { grid-column: 1; grid-row: 2; }
        .ptz.stop { grid-column: 2; grid-row: 2; }
        .ptz.right { grid-column: 3; grid-row: 2; }
        .ptz.down { grid-column: 2; grid-row: 3; }
        .ptz ha-icon { --mdc-icon-size: 26px; }
        .ptz.stop ha-icon { --mdc-icon-size: 19px; }

        .features {
          display: flex;
          gap: 8px;
          padding: 10px 12px 12px;
          overflow-x: auto;
          scrollbar-width: none;
        }
        .features::-webkit-scrollbar { display: none; }
        .feature {
          border: 1px solid var(--divider-color);
          border-radius: 18px;
          background: transparent;
          color: var(--primary-text-color);
          padding: 7px 10px;
          white-space: nowrap;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font: inherit;
          cursor: pointer;
        }
        .feature.on {
          color: var(--primary-color);
          border-color: var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 10%, transparent);
        }
        .feature ha-icon { --mdc-icon-size: 20px; }
        .unavailable {
          position: absolute;
          inset: 0;
          z-index: 8;
          display: none;
          align-items: center;
          justify-content: center;
          color: white;
          background: rgba(0, 0, 0, 0.62);
          font-size: 14px;
        }
        .unavailable.show { display: flex; }
      </style>

      <ha-card>
        <div class="stage">
          <img class="stream" alt="Tenda camera stream">
          <div class="title">Tenda Camera</div>

          <div class="events">
            <div class="event motion">
              <ha-icon icon="mdi:motion-sensor"></ha-icon>
              <span>Движение</span>
            </div>
            <div class="event person">
              <ha-icon icon="mdi:account-alert"></ha-icon>
              <span>Человек</span>
            </div>
          </div>

          <div class="joystick">
            <button class="ptz up" data-dir="up" title="Вверх">
              <ha-icon icon="mdi:chevron-up"></ha-icon>
            </button>
            <button class="ptz left" data-dir="left" title="Влево">
              <ha-icon icon="mdi:chevron-left"></ha-icon>
            </button>
            <button class="ptz stop" data-stop title="Стоп">
              <ha-icon icon="mdi:stop"></ha-icon>
            </button>
            <button class="ptz right" data-dir="right" title="Вправо">
              <ha-icon icon="mdi:chevron-right"></ha-icon>
            </button>
            <button class="ptz down" data-dir="down" title="Вниз">
              <ha-icon icon="mdi:chevron-down"></ha-icon>
            </button>
          </div>

          <div class="unavailable">Поток недоступен</div>
        </div>

        <div class="features">
          <button class="feature motion-toggle" data-feature="motion">
            <ha-icon icon="mdi:motion-sensor"></ha-icon>
            <span>Движение</span>
          </button>
          <button class="feature human-toggle" data-feature="human_detection">
            <ha-icon icon="mdi:account-search"></ha-icon>
            <span>Человек</span>
          </button>
          <button class="feature tracking-toggle" data-feature="human_tracking">
            <ha-icon icon="mdi:account-arrow-right"></ha-icon>
            <span>Слежение</span>
          </button>
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll("[data-dir]").forEach((button) => {
      button.addEventListener("pointerdown", (ev) => {
        ev.preventDefault();
        button.setPointerCapture?.(ev.pointerId);
        this._startPtz(button.dataset.dir);
      });
      for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
        button.addEventListener(type, (ev) => {
          ev.preventDefault();
          this._stopPtz();
        });
      }
    });

    this.shadowRoot
      .querySelector("[data-stop]")
      .addEventListener("click", () => this._stopPtz());

    this.shadowRoot.querySelectorAll("[data-feature]").forEach((button) => {
      button.addEventListener("click", () => {
        const state = this._cameraState();
        if (!state) return;
        const feature = button.dataset.feature;
        const attr = {
          motion: "motion_detection",
          human_detection: "human_detection",
          human_tracking: "human_tracking",
        }[feature];
        const enabled = !Boolean(state.attributes?.[attr]);
        this._hass.callService("tenda_camera", "set_feature", {
          entity_id: this._config.entity,
          feature,
          enabled,
        });
      });
    });
  }

  _cameraState() {
    return this._hass?.states?.[this._config?.entity];
  }

  _startPtz(direction) {
    if (!this._hass || !this._config?.entity) return;
    this._ptzActive = true;
    this._hass.callService("tenda_camera", "ptz", {
      entity_id: this._config.entity,
      action: "start",
      direction,
      speed: 0.28,
      duration: 10,
    });
  }

  _stopPtz() {
    if (!this._hass || !this._config?.entity) return;
    if (!this._ptzActive) {
      this._hass.callService("tenda_camera", "ptz", {
        entity_id: this._config.entity,
        action: "stop",
      });
      return;
    }
    this._ptzActive = false;
    this._hass.callService("tenda_camera", "ptz", {
      entity_id: this._config.entity,
      action: "stop",
    });
  }

  _setActive(selector, active) {
    this.shadowRoot.querySelector(selector)?.classList.toggle("on", Boolean(active));
  }

  _update() {
    if (!this.shadowRoot || !this._hass || !this._config?.entity) return;

    const state = this._cameraState();
    const unavailable = !state || ["unavailable", "unknown"].includes(state.state);

    this.shadowRoot
      .querySelector(".unavailable")
      ?.classList.toggle("show", unavailable);

    if (!state) return;

    const token = state.attributes?.access_token;
    if (token) {
      const url =
        `/api/camera_proxy_stream/${state.entity_id}?token=${encodeURIComponent(token)}`;
      if (url !== this._streamUrl) {
        this._streamUrl = url;
        this.shadowRoot.querySelector("img.stream").src = url;
      }
    }

    const title =
      this._config.name ||
      state.attributes?.friendly_name ||
      "Tenda Camera";
    this.shadowRoot.querySelector(".title").textContent = title;

    this._setActive(".motion-toggle", state.attributes?.motion_detection);
    this._setActive(".human-toggle", state.attributes?.human_detection);
    this._setActive(".tracking-toggle", state.attributes?.human_tracking);

    this.shadowRoot
      .querySelector(".event.motion")
      ?.classList.toggle("active", Boolean(state.attributes?.motion_detected));
    this.shadowRoot
      .querySelector(".event.person")
      ?.classList.toggle("active", Boolean(state.attributes?.person_detected));
  }
}

customElements.define("tenda-camera-card", TendaCameraCard);

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "tenda-camera-card")) {
  window.customCards.push({
    type: "tenda-camera-card",
    name: "Tenda Camera",
    description: "Live Tenda camera view with touch PTZ controls and detection switches.",
    preview: true,
  });
}
