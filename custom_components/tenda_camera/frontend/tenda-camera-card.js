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
    this._fullscreenAspectRatio = null;
    this._fullscreenFillTimers = [];
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
    this._clearFullscreenFillTimers();
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

  _fullscreenLandscapeSize() {
    const viewportWidth = Math.max(window.innerWidth, 1);
    const viewportHeight = Math.max(window.innerHeight, 1);

    if (viewportWidth >= viewportHeight) {
      return {
        width: viewportWidth,
        height: viewportHeight,
        rotate: false,
      };
    }

    // Even when Android auto-rotate is disabled, render the fullscreen layer
    // in a landscape coordinate system and rotate it ourselves.
    return {
      width: viewportHeight,
      height: viewportWidth,
      rotate: true,
    };
  }

  _getFullscreenAspectRatio() {
    const { width, height } = this._fullscreenLandscapeSize();
    return `${width}:${height}`;
  }

  _applyFullscreenGeometry() {
    const stage = this.shadowRoot?.querySelector(".fullscreen-stage");
    if (!stage) return;

    const { width, height, rotate } = this._fullscreenLandscapeSize();
    stage.style.width = `${width}px`;
    stage.style.height = `${height}px`;
    stage.classList.toggle("force-rotate", rotate);
  }

  _clearFullscreenFillTimers() {
    for (const timer of this._fullscreenFillTimers) {
      window.clearTimeout(timer);
    }
    this._fullscreenFillTimers = [];
  }

  async _forceFullscreenCardFill(card) {
    if (!card) return;

    try {
      await card.updateComplete;

      card.style.position = "absolute";
      card.style.inset = "0";
      card.style.width = "100%";
      card.style.height = "100%";
      card.style.margin = "0";
      card.style.borderRadius = "0";
      card.style.overflow = "hidden";
      card.style.background = "#000";

      const cardRoot = card.shadowRoot;
      const haCard = cardRoot?.querySelector("ha-card");
      if (haCard) {
        haCard.style.position = "absolute";
        haCard.style.inset = "0";
        haCard.style.width = "100%";
        haCard.style.height = "100%";
        haCard.style.minHeight = "0";
        haCard.style.margin = "0";
        haCard.style.borderRadius = "0";
        haCard.style.overflow = "hidden";
        haCard.style.background = "#000";
      }

      const imageContainer = cardRoot?.querySelector(".image-container");
      if (imageContainer) {
        imageContainer.style.position = "absolute";
        imageContainer.style.inset = "0";
        imageContainer.style.width = "100%";
        imageContainer.style.height = "100%";
        imageContainer.style.minHeight = "0";
        imageContainer.style.overflow = "hidden";
        imageContainer.style.background = "#000";
      }

      const huiImage = cardRoot?.querySelector("hui-image");
      if (!huiImage) return;

      huiImage.style.position = "absolute";
      huiImage.style.inset = "0";
      huiImage.style.width = "100%";
      huiImage.style.height = "100%";
      huiImage.style.minHeight = "0";
      huiImage.style.background = "#000";
      await huiImage.updateComplete;

      const imageRoot = huiImage.shadowRoot;
      const container = imageRoot?.querySelector(".container");
      if (container) {
        container.style.position = "absolute";
        container.style.inset = "0";
        container.style.width = "100%";
        container.style.height = "100%";
        container.style.paddingBottom = "0";
        container.style.background = "#000";
        container.style.overflow = "hidden";
      }

      const stream = imageRoot?.querySelector("ha-camera-stream");
      if (!stream) return;

      stream.style.position = "absolute";
      stream.style.inset = "0";
      stream.style.width = "100%";
      stream.style.height = "100%";
      stream.fitMode = "cover";
      stream.aspectRatio = undefined;
      await stream.updateComplete;

      const streamRoot = stream.shadowRoot;
      for (const child of streamRoot?.querySelectorAll(
        "img, ha-hls-player, ha-web-rtc-player"
      ) || []) {
        child.style.position = "absolute";
        child.style.inset = "0";
        child.style.width = "100%";
        child.style.height = "100%";
        child.style.margin = "0";

        if ("fitMode" in child) {
          child.fitMode = "cover";
        }
        if ("aspectRatio" in child) {
          child.aspectRatio = undefined;
        }

        if (child.updateComplete) {
          await child.updateComplete;
        }

        const video = child.shadowRoot?.querySelector("video");
        if (video) {
          video.style.position = "absolute";
          video.style.inset = "0";
          video.style.width = "100%";
          video.style.height = "100%";
          video.style.maxWidth = "none";
          video.style.maxHeight = "none";
          video.style.objectFit = "cover";
          video.style.aspectRatio = "auto";
          video.style.margin = "0";
        }
      }
    } catch (err) {
      console.debug("Tenda Camera: fullscreen fill adjustment skipped", err);
    }
  }

  _scheduleFullscreenFill(card) {
    this._clearFullscreenFillTimers();
    for (const delay of [0, 120, 450, 1200]) {
      const timer = window.setTimeout(
        () => this._forceFullscreenCardFill(card),
        delay
      );
      this._fullscreenFillTimers.push(timer);
    }
  }

  _resetFullscreenCameraCard() {
    this._clearFullscreenFillTimers();
    this._fullscreenCameraGeneration += 1;
    this._fullscreenCameraCard = null;
    this._fullscreenCameraEntity = null;
    this._fullscreenAspectRatio = null;
    this.shadowRoot
      ?.querySelector(".fullscreen-camera-host")
      ?.replaceChildren();
  }

  async _ensureFullscreenCameraCard(state) {
    const host = this.shadowRoot?.querySelector(".fullscreen-camera-host");
    if (!host || !state || !this._hass) return;

    const aspectRatio = this._getFullscreenAspectRatio();

    if (
      this._fullscreenCameraCard &&
      this._fullscreenCameraEntity === state.entity_id &&
      this._fullscreenAspectRatio === aspectRatio
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
        fit_mode: "cover",
        aspect_ratio: aspectRatio,
        tap_action: { action: "none" },
        hold_action: { action: "none" },
      });

      card.hass = this._hass;
      card.style.width = "100%";
      card.style.height = "100%";
      card.style.display = "block";
      card.style.background = "#000";
      card.style.setProperty("--ha-card-background", "#000");
      card.style.setProperty("--card-background-color", "#000");
      card.style.setProperty("--ha-card-border-radius", "0px");
      card.style.setProperty("--ha-card-box-shadow", "none");

      host.replaceChildren(card);
      this._fullscreenCameraCard = card;
      this._fullscreenCameraEntity = state.entity_id;
      this._fullscreenAspectRatio = aspectRatio;
      this._scheduleFullscreenFill(card);
    } catch (err) {
      console.error("Tenda Camera: failed to mount fullscreen live card", err);
      host.textContent = "Не удалось открыть основной поток";
      host.style.color = "white";
      host.style.display = "grid";
      host.style.placeItems = "center";
    }
  }

  async _openFullscreen() {
    const overlay = this.shadowRoot?.querySelector(".fullscreen-overlay");
    const state = this._mainCameraState();
    if (!overlay || !state) return;

    overlay.classList.add("show");
    this._applyFullscreenGeometry();

    // Enter real browser/WebView fullscreen first. Android WebView only allows
    // orientation locking reliably while an element is fullscreen.
    try {
      if (overlay.requestFullscreen && !document.fullscreenElement) {
        await overlay.requestFullscreen();
      }
    } catch (_err) {
      // Keep the full-viewport overlay as a fallback.
    }

    try {
      if (screen.orientation?.lock) {
        await screen.orientation.lock("landscape");
      }
    } catch (_err) {
      // We do not depend on Android auto-rotate. If orientation lock is not
      // allowed by the WebView, CSS rotates the landscape stage itself.
    }

    this._applyFullscreenGeometry();

    // Let the viewport settle after the fullscreen/orientation transition,
    // then create the high-quality main-stream card for the final ratio.
    await new Promise((resolve) =>
      window.requestAnimationFrame(() =>
        window.requestAnimationFrame(resolve)
      )
    );

    this._applyFullscreenGeometry();
    this._resetFullscreenCameraCard();
    await this._ensureFullscreenCameraCard(state);
  }

  async _closeFullscreen() {
    const overlay = this.shadowRoot?.querySelector(".fullscreen-overlay");
    overlay?.classList.remove("show");

    try {
      screen.orientation?.unlock?.();
    } catch (_err) {
      // Ignore unsupported orientation APIs.
    }

    try {
      if (document.fullscreenElement && document.exitFullscreen) {
        await document.exitFullscreen();
      }
    } catch (_err) {
      // Nothing else to do.
    }

    this._resetFullscreenCameraCard();
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
          top: auto;
          right: 12px;
          bottom: 12px;
          z-index: 7;
          width: 40px;
          height: 40px;
          border: 0;
          border-radius: 8px;
          color: white;
          background: rgba(0, 0, 0, 0.42);
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
          width: 100vw;
          height: 100vh;
          margin: 0;
          padding: 0;
          overflow: hidden;
          background: #000;
        }
        .fullscreen-overlay.show {
          display: block;
        }
        .fullscreen-stage {
          position: absolute;
          left: 50%;
          top: 50%;
          transform: translate(-50%, -50%);
          transform-origin: center center;
          overflow: hidden;
          background: #000;
          touch-action: none;
        }
        .fullscreen-stage.force-rotate {
          transform: translate(-50%, -50%) rotate(90deg);
        }
        .fullscreen-camera-host {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
          overflow: hidden;
          background: #000;
        }
        .fullscreen-camera-host > * {
          width: 100% !important;
          height: 100% !important;
          min-height: 100% !important;
          display: block;
          margin: 0 !important;
          border-radius: 0 !important;
          background: #000 !important;
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
        .fullscreen-stage .joystick {
          left: 18px;
          right: auto;
          bottom: 18px;
          z-index: 100002;
        }
        .events {
          position: absolute;
          left: 12px;
          top: 12px;
          bottom: auto;
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
          left: 12px;
          right: auto;
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
          <div class="fullscreen-stage">
            <div class="fullscreen-camera-host"></div>

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

          <button class="fullscreen-close" data-fullscreen-close title="Закрыть">
            <ha-icon icon="mdi:close"></ha-icon>
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
        try {
          screen.orientation?.unlock?.();
        } catch (_err) {
          // Ignore unsupported orientation APIs.
        }
        this._resetFullscreenCameraCard();
      }
    });

    const refreshFullscreenLayout = () => {
      const overlay = this.shadowRoot?.querySelector(".fullscreen-overlay");
      if (!overlay?.classList.contains("show")) return;

      const state = this._mainCameraState();
      if (!state) return;

      window.setTimeout(() => {
        this._applyFullscreenGeometry();
        this._resetFullscreenCameraCard();
        this._ensureFullscreenCameraCard(state);
      }, 120);
    };

    window.addEventListener("orientationchange", refreshFullscreenLayout);
    window.addEventListener("resize", refreshFullscreenLayout);

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

  _previewCameraState() {
    if (!this._hass) return this._cameraState();

    return (
      Object.values(this._hass.states || {}).find(
        (state) =>
          state.entity_id.startsWith("camera.") &&
          state.attributes?.brand === "Tenda" &&
          state.attributes?.stream_role === "sub"
      ) || this._cameraState() || this._mainCameraState()
    );
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

    const controlState = this._cameraState();
    const previewState = this._previewCameraState();
    const unavailable =
      !previewState ||
      ["unavailable", "unknown"].includes(previewState.state);

    this.shadowRoot
      .querySelector(".unavailable")
      ?.classList.toggle("show", unavailable);

    if (!controlState || !previewState) return;

    // Dashboard view is always the lighter RP7 sub-stream. The fullscreen
    // button intentionally switches to the main stream.
    this._ensureNativeCameraCard(previewState);
    if (this._nativeCameraCard) {
      this._nativeCameraCard.hass = this._hass;
    }
    if (this._fullscreenCameraCard) {
      this._fullscreenCameraCard.hass = this._hass;
    }

    this._setActive(
      ".motion-toggle",
      controlState.attributes?.motion_detection
    );
    this._setActive(
      ".human-toggle",
      controlState.attributes?.human_detection
    );
    this._setActive(
      ".tracking-toggle",
      controlState.attributes?.human_tracking
    );

    this.shadowRoot
      .querySelector(".event.motion")
      ?.classList.toggle(
        "active",
        Boolean(controlState.attributes?.motion_detected)
      );
    this.shadowRoot
      .querySelector(".event.person")
      ?.classList.toggle(
        "active",
        Boolean(controlState.attributes?.person_detected)
      );
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
