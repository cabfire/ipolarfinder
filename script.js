const MIN_ZOOM = 1.0;
const MAX_ZOOM = 5.0;
const ZOOM_STEP = 0.5;
const FOCUS_STEP = 0.0125;
const MIN_FOCUS = 0.0;
const MAX_FOCUS = 10.0;
const MIN_LONGITUDE = -180.0;
const MAX_LONGITUDE = 180.0;
const restartBtn = document.getElementById("restartBtn");
const shutdownBtn = document.getElementById("shutdownBtn");

let eventSource = null;
let lastFrameVersion = -1;
let zoom = 1.0;
let nightMode = false;
let autofocus = true;
let focusValue = 0.0;
let longitudeDeg = 2.0;
let autoExposure = true;
let exposureMs = 500;
let gainValue = 8.0;
let liveStackingEnabled = true;
let liveStackingAlpha = 0.8;
let autoStretchEnabled = false;
let blackpointRemovalEnabled = true;
let stretchGamma = 2.2;
let stretchSigmaK = 1.8;
let constellationEnabled = true;
let distortionK1 = 0.10;
let distortionK2 = 0.00;
let histogramEnabled = true;

restartBtn.addEventListener("click", async () => {
  const ok = confirm("Restart the Polaris service?");
  if (!ok) return;

  try {
    await fetch("/restart_system", { method: "POST" });
  } catch (err) {
    console.error("restart failed", err);
  }
});

shutdownBtn.addEventListener("click", async () => {
  const ok = confirm("Shutdown the Raspberry Pi?");
  if (!ok) return;

  try {
    await fetch("/shutdown_system", { method: "POST" });
  } catch (err) {
    console.error("shutdown failed", err);
  }
});

function toggleLiveStacking() {
    liveStackingEnabled = document.getElementById("stackToggle").checked;
    updateProcessingUI();
    sendProcessingConfig();
}

function changeStackAlpha() {
    const value = parseFloat(document.getElementById("stackAlphaSlider").value);
    if (!Number.isNaN(value)) {
        liveStackingAlpha = Math.max(0.1, Math.min(0.95, value));
        updateProcessingUI();
        sendProcessingConfig();
    }
}

function toggleAutoStretch() {
    autoStretchEnabled = document.getElementById("stretchToggle").checked;
    updateProcessingUI();
    sendProcessingConfig();
}

function toggleBlackpoint() {
    blackpointRemovalEnabled = document.getElementById("blackpointToggle").checked;
    updateProcessingUI();
    sendProcessingConfig();
}

function toggleConstellation() {
    constellationEnabled = document.getElementById("constellationToggle").checked;
    updateProcessingUI();
    sendProcessingConfig();
}

function changeDistortionK1() {
    const value = parseFloat(document.getElementById("distortionK1Slider").value);
    if (!Number.isNaN(value)) {
        distortionK1 = Math.max(-1.0, Math.min(1.0, value));
        updateProcessingUI();
        sendProcessingConfig();
    }
}

function changeDistortionK2() {
    const value = parseFloat(document.getElementById("distortionK2Slider").value);
    if (!Number.isNaN(value)) {
        distortionK2 = Math.max(-1.0, Math.min(1.0, value));
        updateProcessingUI();
        sendProcessingConfig();
    }
}

function toggleHistogram() {
    histogramEnabled = document.getElementById("histogramToggle").checked;
    updateProcessingUI();
    sendProcessingConfig();
}

function changeGamma() {
    const value = parseFloat(document.getElementById("gammaInput").value);
    if (!Number.isNaN(value)) {
        stretchGamma = Math.max(0.1, Math.min(5.0, value));
        updateProcessingUI();
        sendProcessingConfig();
    }
}

function changeSigmaK() {
    const value = parseFloat(document.getElementById("sigmaKInput").value);
    if (!Number.isNaN(value)) {
        stretchSigmaK = Math.max(0.0, Math.min(10.0, value));
        updateProcessingUI();
        sendProcessingConfig();
    }
}

function updateAEControls() {
    document.getElementById("exposureSlider").disabled = autoExposure;
    document.getElementById("gainSlider").disabled = autoExposure;
}

function updateExposureLabel() {
    document.getElementById("exposureValue").textContent = exposureMs.toString();
}

function updateGainLabel() {
    document.getElementById("gainValue").textContent = gainValue.toFixed(1);
}

function toggleAE() {
    autoExposure = document.getElementById("aeToggle").checked;
    updateAEControls();

    fetch("/set_exposure_mode?ae=" + (autoExposure ? "1" : "0"))
        .then(() => refreshImage())
        .catch(() => {});
}

function changeExposure() {
    exposureMs = parseInt(document.getElementById("exposureSlider").value, 10);
    updateExposureLabel();

    if (!autoExposure) {
        fetch("/set_camera?exp_ms=" + exposureMs + "&gain=" + gainValue.toFixed(1))
            .then(() => refreshImage())
            .catch(() => {});
    }
}

function changeGain() {
    gainValue = parseFloat(document.getElementById("gainSlider").value);
    updateGainLabel();

    if (!autoExposure) {
        fetch("/set_camera?exp_ms=" + exposureMs + "&gain=" + gainValue.toFixed(1))
            .then(() => refreshImage())
            .catch(() => {});
    }
}

function clampZoom(value) {
    value = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value));
    return Math.round(value * 2) / 2;
}

function clampFocus(value) {
    return Math.max(MIN_FOCUS, Math.min(MAX_FOCUS, value));
}

function clampLongitude(value) {
    return Math.max(MIN_LONGITUDE, Math.min(MAX_LONGITUDE, value));
}

function updateZoomLabel() {
    document.getElementById("zoomValue").textContent = zoom.toFixed(1);
}

function formatFocusDistance(value) {
    if (value <= 0.0001) {
        return "∞";
    }
    return (1.0 / value).toFixed(0) + "m";
}

function updateFocusLabel() {
    document.getElementById("focusValue").textContent = focusValue.toFixed(3);
    document.getElementById("focusDistance").textContent = formatFocusDistance(focusValue);
}

function updateLongitudeLabel() {
    document.getElementById("longitudeInput").value = longitudeDeg.toFixed(3);
}

function updateButtons() {
    document.getElementById("zoomMinusBtn").disabled = (zoom <= MIN_ZOOM);
    document.getElementById("zoomPlusBtn").disabled = (zoom >= MAX_ZOOM);
    document.getElementById("zoomMinBtn").disabled = (zoom <= MIN_ZOOM);
    document.getElementById("zoomMaxBtn").disabled = (zoom >= MAX_ZOOM);

    const focusDisabled = autofocus;
    document.getElementById("focusMinusBtn").disabled = focusDisabled || focusValue <= MIN_FOCUS;
    document.getElementById("focusInfinityBtn").disabled = focusDisabled || focusValue === 0.0;
    document.getElementById("focusPlusBtn").disabled = focusDisabled || focusValue >= MAX_FOCUS;
}

function updateProcessingUI() {
    document.getElementById("stackToggle").checked = liveStackingEnabled;
    document.getElementById("stackAlphaSlider").value = liveStackingAlpha.toFixed(2);
    document.getElementById("stackAlphaValue").textContent = liveStackingAlpha.toFixed(2);
    document.getElementById("stackAlphaSlider").disabled = !liveStackingEnabled;
    document.getElementById("stretchToggle").checked = autoStretchEnabled;
    document.getElementById("blackpointToggle").checked = blackpointRemovalEnabled;
    document.getElementById("constellationToggle").checked = constellationEnabled;
    document.getElementById("distortionK1Slider").value = distortionK1.toFixed(2);
    document.getElementById("distortionK2Slider").value = distortionK2.toFixed(2);
    document.getElementById("distortionK1Value").textContent = distortionK1.toFixed(2);
    document.getElementById("distortionK2Value").textContent = distortionK2.toFixed(2);
    document.getElementById("distortionK1Slider").disabled = !constellationEnabled;
    document.getElementById("distortionK2Slider").disabled = !constellationEnabled;
    document.getElementById("distortionControls").style.display = constellationEnabled ? "block" : "none";
    document.getElementById("histogramToggle").checked = histogramEnabled;
    document.getElementById("gammaInput").value = stretchGamma.toFixed(1);
    document.getElementById("sigmaKInput").value = stretchSigmaK.toFixed(1);

    document.getElementById("stretchControls").style.display =
        autoStretchEnabled ? "block" : "none";
}

function updateUI() {
    updateZoomLabel();
    updateFocusLabel();
    updateLongitudeLabel();
    updateButtons();
    updateExposureLabel();
    updateGainLabel();
    updateAEControls();
    updateProcessingUI();
}

function refreshImage(version = null) {
    const img = document.getElementById("img");

    if (version !== null) {
        img.src = "/polaris.jpg?v=" + encodeURIComponent(version);
    } else {
        img.src = "/polaris.jpg?t=" + Date.now();
    }
}

function zoomPlus() {
    zoom = clampZoom(zoom + ZOOM_STEP);
    updateUI();

    fetch("/set_zoom?zoom=" + zoom)
        .then(() => refreshImage())
        .catch(() => {});
}

function zoomMinus() {
    zoom = clampZoom(zoom - ZOOM_STEP);
    updateUI();

    fetch("/set_zoom?zoom=" + zoom)
        .then(() => refreshImage())
        .catch(() => {});
}

function zoomMin() {
    zoom = MIN_ZOOM;
    updateUI();

    fetch("/set_zoom?zoom=" + zoom)
        .then(() => refreshImage())
        .catch(() => {});
}

function zoomMax() {
    zoom = MAX_ZOOM;
    updateUI();

    fetch("/set_zoom?zoom=" + zoom)
        .then(() => refreshImage())
        .catch(() => {});
}

function toggleNightMode() {
    nightMode = document.getElementById("nightModeToggle").checked;
    document.body.classList.toggle("night-mode", nightMode);

    fetch("/set_mode?night=" + (nightMode ? "1" : "0"))
        .then(() => refreshImage())
        .catch(() => {});
}

function toggleAF() {
    autofocus = document.getElementById("afToggle").checked;

    fetch("/set_af?af=" + (autofocus ? "1" : "0"))
        .then(() => {
            updateUI();
            refreshImage();
        })
        .catch(() => {});
}

function focusPlus() {
    if (autofocus) return;
    focusValue = clampFocus(focusValue + FOCUS_STEP);
    updateUI();

    fetch("/set_focus?delta=" + FOCUS_STEP.toFixed(4))
        .then(() => refreshImage())
        .catch(() => {});
}

function focusMinus() {
    if (autofocus) return;
    focusValue = clampFocus(focusValue - FOCUS_STEP);
    updateUI();

    fetch("/set_focus?delta=-" + FOCUS_STEP.toFixed(4))
        .then(() => refreshImage())
        .catch(() => {});
}

function focusInfinity() {
    if (autofocus) return;
    focusValue = 0.0;
    updateUI();

    fetch("/set_focus?lens=0.0")
        .then(() => refreshImage())
        .catch(() => {});
}

function setLongitude() {
    const raw = parseFloat(document.getElementById("longitudeInput").value);
    if (Number.isNaN(raw)) {
        updateLongitudeLabel();
        return;
    }

    longitudeDeg = clampLongitude(raw);
    updateUI();

    fetch("/set_longitude?lon=" + longitudeDeg.toFixed(6))
        .then(() => refreshImage())
        .catch(() => {});
}

function sendProcessingConfig() {
    const url =
        "/set_processing"
        + "?stack=" + (liveStackingEnabled ? "1" : "0")
        + "&stack_alpha=" + encodeURIComponent(liveStackingAlpha.toFixed(2))
        + "&stretch=" + (autoStretchEnabled ? "1" : "0")
        + "&blackpoint=" + (blackpointRemovalEnabled ? "1" : "0")
        + "&constellation=" + (constellationEnabled ? "1" : "0")
        + "&distortion_k1=" + encodeURIComponent(distortionK1.toFixed(2))
        + "&distortion_k2=" + encodeURIComponent(distortionK2.toFixed(2))
        + "&histogram=" + (histogramEnabled ? "1" : "0")
        + "&gamma=" + encodeURIComponent(stretchGamma.toFixed(2))
        + "&sigma_k=" + encodeURIComponent(stretchSigmaK.toFixed(2));

    fetch(url)
        .then(() => refreshImage())
        .catch(() => {});
}

function toggleMenu() {
    const collapsed = document.body.classList.toggle("menu-collapsed");
    localStorage.setItem("menuCollapsed", collapsed ? "1" : "0");
}

function loadPreferences() {
    const savedMenuCollapsed = localStorage.getItem("menuCollapsed");
    if (savedMenuCollapsed === "1") {
        document.body.classList.add("menu-collapsed");
    }
}

async function loadServerConfig() {
    try {
        const response = await fetch("/config?t=" + Date.now());
        const cfg = await response.json();

        nightMode = cfg.night_mode_enabled;
        autofocus = cfg.autofocus_enabled;
        focusValue = cfg.lens_position;
        longitudeDeg = cfg.longitude_deg;
        zoom = cfg.zoom_level;
        liveStackingEnabled = cfg.live_stacking_enabled ?? true;
        liveStackingAlpha = cfg.live_stacking_alpha ?? 0.8;
        autoStretchEnabled = cfg.auto_stretch_enabled ?? false;
        blackpointRemovalEnabled = cfg.blackpoint_removal_enabled ?? true;
        stretchGamma = cfg.stretch_gamma ?? 2.2;
        stretchSigmaK = cfg.stretch_sigma_k ?? 1.8;
        constellationEnabled = cfg.constellation_enabled ?? true;
        distortionK1 = cfg.distortion_k1 ?? 0.10;
        distortionK2 = cfg.distortion_k2 ?? 0.00;
        histogramEnabled = cfg.histogram_enabled ?? true;
        autoExposure = cfg.auto_exposure_enabled;
        exposureMs = Math.round(cfg.exposure_time_us / 1000);
        gainValue = cfg.analogue_gain;

        document.getElementById("nightModeToggle").checked = nightMode;
        document.getElementById("afToggle").checked = autofocus;
        document.getElementById("aeToggle").checked = autoExposure;
        document.getElementById("constellationToggle").checked = constellationEnabled;
        document.getElementById("histogramToggle").checked = histogramEnabled;
        document.getElementById("longitudeInput").value = longitudeDeg.toFixed(3);
        document.getElementById("exposureSlider").value = exposureMs;
        document.getElementById("gainSlider").value = gainValue;
        document.getElementById("zoomValue").textContent = zoom.toFixed(1);

        document.body.classList.toggle("night-mode", nightMode);
        updateUI();
    } catch (err) {
        console.log("Unable to load /config", err);
    }
}

function connectSSE() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource("/events");

    eventSource.addEventListener("frame", (event) => {
        try {
            const payload = JSON.parse(event.data);
            const version = payload.version;

            if (version !== lastFrameVersion) {
                lastFrameVersion = version;
                refreshImage(version);
            }
        } catch (err) {
            console.log("Invalid SSE payload", err);
        }
    });

    eventSource.onerror = () => {
        console.log("SSE disconnected, browser will retry automatically");
    };
}

window.onload = async function () {
    loadPreferences();
    await loadServerConfig();
    refreshImage();
    connectSSE();
};
