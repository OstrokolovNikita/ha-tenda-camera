class TendaCameraCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._ptzTimer = null;
    this._ptzDirection = null;
    this._ptzActive = false;
    this._nativeCameraCard = null;
    this._nativeCameraEntity = null;
    this._nativeCameraGeneration = 0;
    this._fullscreenCameraCard = null;
    this._fullscreenCameraEntity = null;
    this._fullscreenCameraGeneration = 0;
    this._render();
  }

  static getStubConfig(hass) {
    const tendaCameras = Object.values(hass.states || {}).filter(
      (state) =>
        state.entity_id.startsWith("camera.") &&
        state.attributes?.brand === "Tenda"
    );
    const entity =
      tendaCameras.find(
        (state) =>
          state.attributes?.stream_role === "main" &&
          state.attributes?.stream_codec === "H.264"
      ) ||
      tendaCameras.find(
        (state) =>
          state.attributes?.stream_role === "sub" &&
          state.attributes?.stream_codec === "H.264"
      ) ||
      tendaCameras.find((state) => state.attributes?.stream_role === "main") ||
      tendaCameras.find((state) => state.attributes?.stream_role === "sub");
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

  disconnectedCallback() {
    this._stopPtzTimerOnly();
    this._nativeCameraGeneration += 1;
    this._fullscreenCameraGeneration += 1;
  }

  async _ensureNativeCameraCard(state) {
    const host = this.shadowRoot?.querySelector(".native-camera-host");
    if (!host || !state || !this._hass) return;

    if (
      this._nativeCameraCard &&
      this._nativeCameraEntity === state.entity_id
    ) {
      this._nativeCameraCard.hass = this._hass;
      return;
    }

    const generation = ++this._nativeCameraGeneration;

    try {
      if (typeof window.loadCardHelpers !== "function") {
        throw new Error("Home Assistant card helpers are unavailable");
      }

      const helpers = await window.loadCardHelpers();
      if (generation !== this._nativeCameraGeneration) return;

      const card = helpers.createCardElement({
        type: "picture-entity",
        entity: state.entity_id,
        camera_image: state.entity_id,
        camera_view: "live",
        show_name: false,
        show_state: false,
        fit_mode: "cover",
        tap_action: { action: "none" },
        hold_action: { action: "none" },
      });

      card.hass = this._hass;
      card.style.width = "100%";
      card.style.height = "100%";
      card.style.display = "block";

      host.replaceChildren(card);
      this._nativeCameraCard = card;
      this._nativeCameraEntity = state.entity_id;
    } catch (err) {
      console.error("Tenda Camera: failed to mount native live card", err);
      host.textContent = "Не удалось открыть live-поток";
      host.style.color = "white";
      host.style.display = "grid";
      host.style.placeItems = "center";
    }
  }

  _mainCameraState() {
    if (!this._hass) return null;

    return (
      Object.values(this._hass.states || {}).find(
        (state) =>
          state.entity_id.startsWith("camera.") &&
          state.attributes?.brand === "Tenda" &&
          state.attributes?.stream_role === "main"
      ) || this._cameraState()
    );
  }

  async _ensureFullscreenCameraCard(state) {
    const host = this.shadowRoot?.querySelector(".fullscreen-camera-host");
    if (!host || !state || !this._hass) return;

    if (
      this._fullscreenCameraCard &&
      this._fullscreenCameraEntity === state.entity_id
    ) {
      this._fullscreenCameraCard.hass = this._hass;
      return;
    }

    const generation = ++this._fullscreenCameraGeneration;

    try {
      if (typeof window.loadCardHelpers !== "function") {
        throw new Error("Home Assistant card helpers are unavailable");
      }

      const helpers = await window.loadCardHelpers();
      if (generation !== this._fullscreenCameraGeneration) return;

      const card = helpers.createCardElement({
        type: "picture-entity",
        entity: state.entity_id,
        camera_image: state.entity_id,
        camera_view: "live",
        show_name: false,
        show_state: false,
        fit_mode: "contain",
        tap_action: { action: "none" },
        hold_action: { action: "none" },
      });

      card.hass = this._hass;
      card.style.width = "100%";
      card.style.height = "100%";
      card.style.display = "block";
      card.style.background = "#000";

      host.replaceChildren(card);
      this._fullscreenCameraCard = card;
      this._fullscreenCameraEntity = state.entity_id;
    } catch (err) {
      console.error("Tenda Camera: failed to mount fullscreen live card", err);
      host.textContent = "Не удалось открыть основной поток";
      host.style.color = "white";
      host.style.display = "grid";
      host.style.placeItems = "center";
    }
  }

  _openFullscreen() {
    const overlay = this.shadowRoot?.querySelector(".fullscreen-overlay");
    const state = this._mainCameraState();
    if (!overlay || !state) return;

    overlay.classList.add("show");
    this._ensureFullscreenCameraCard(state);

    if (overlay.requestFullscreen && !document.fullscreenElement) {
      const request = overlay.requestFullscreen();
      if (request?.catch) {
        request.catch(() => {});
      }
    }
  }

  _closeFullscreen() {
    const overlay = this.shadowRoot?.querySelector(".fullscreen-overlay");
    overlay?.classList.remove("show");

    if (document.fullscreenElement && document.exitFullscreen) {
      const exit = document.exitFullscreen();
      if (exit?.catch) {
        exit.catch(() => {});
      }
    }
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
        .native-camera-host {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          overflow: hidden;
          background: #111;
        }
        .native-camera-host > * {
          width: 100%;
          height: 100%;
          display: block;
        }
        .fullscreen-button {
          position: absolute;
          top: 12px;
          right: 12px;
          z-index: 7;
          width: 40px;
          height: 40px;
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
        .fullscreen-button ha-icon {
          --mdc-icon-size: 25px;
        }
        .fullscreen-overlay {
          position: fixed;
          inset: 0;
          z-index: 100000;
          display: none;
          background: #000;
        }
        .fullscreen-overlay.show {
          display: block;
        }
        .fullscreen-camera-host {
          position: absolute;
          inset: 0;
          background: #000;
        }
        .fullscreen-camera-host > * {
          width: 100%;
          height: 100%;
          display: block;
        }
        .fullscreen-close {
          position: absolute;
          top: max(12px, env(safe-area-inset-top));
          right: max(12px, env(safe-area-inset-right));
          z-index: 100003;
          width: 44px;
          height: 44px;
          border: 0;
          border-radius: 50%;
          color: white;
          background: rgba(0, 0, 0, 0.58);
          display: grid;
          place-items: center;
          cursor: pointer;
          backdrop-filter: blur(5px);
        }
        .fullscreen-close ha-icon {
          --mdc-icon-size: 28px;
        }
        .fullscreen-overlay .joystick {
          right: max(18px, env(safe-area-inset-right));
          bottom: max(18px, env(safe-area-inset-bottom));
          z-index: 100002;
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
          <div class="native-camera-host"></div>
          <button class="fullscreen-button" data-fullscreen title="На весь экран">
            <ha-icon icon="mdi:fullscreen"></ha-icon>
          </button>

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

        <div class="fullscreen-overlay">
          <div class="fullscreen-camera-host"></div>
          <button class="fullscreen-close" data-fullscreen-close title="Закрыть">
            <ha-icon icon="mdi:close"></ha-icon>
          </button>

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

    this.shadowRoot.querySelectorAll("[data-stop]").forEach((button) => {
      button.addEventListener("click", () => this._stopPtz());
    });

    this.shadowRoot
      .querySelector("[data-fullscreen]")
      ?.addEventListener("click", () => this._openFullscreen());

    this.shadowRoot
      .querySelector("[data-fullscreen-close]")
      ?.addEventListener("click", () => this._closeFullscreen());

    document.addEventListener("fullscreenchange", () => {
      const overlay = this.shadowRoot?.querySelector(".fullscreen-overlay");
      if (overlay?.classList.contains("show") && !document.fullscreenElement) {
        overlay.classList.remove("show");
      }
    });

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

  _ptzPulse() {
    if (
      !this._hass ||
      !this._config?.entity ||
      !this._ptzActive ||
      !this._ptzDirection
    ) {
      return;
    }

    this._hass.callService("tenda_camera", "ptz", {
      entity_id: this._config.entity,
      action: "pulse",
      direction: this._ptzDirection,
      speed: 0.22,
      duration: 0.22,
    });
  }

  _startPtz(direction) {
    if (!this._hass || !this._config?.entity) return;

    this._stopPtzTimerOnly();
    this._ptzActive = true;
    this._ptzDirection = direction;
    this._ptzPulse();

    // ONVIF continuous_duration is limited to <= 1 second by Home Assistant.
    // Repeating short pulses gives smooth press-and-hold movement without
    // violating the service schema.
    this._ptzTimer = window.setInterval(() => this._ptzPulse(), 180);
  }

  _stopPtzTimerOnly() {
    if (this._ptzTimer !== null) {
      window.clearInterval(this._ptzTimer);
      this._ptzTimer = null;
    }
  }

  _stopPtz() {
    if (!this._hass || !this._config?.entity) return;

    this._stopPtzTimerOnly();
    this._ptzActive = false;
    this._ptzDirection = null;

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

    this._ensureNativeCameraCard(state);
    if (this._nativeCameraCard) {
      this._nativeCameraCard.hass = this._hass;
    }
    if (this._fullscreenCameraCard) {
      this._fullscreenCameraCard.hass = this._hass;
    }

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
