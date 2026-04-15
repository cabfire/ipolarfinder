# iPolarFinder (Raspberry Pi)

`iPolarFinder` is a lightweight Raspberry Pi web app for **polar alignment assistance**.
It captures frames from a Pi camera, computes Polaris hour angle from UTC + observer longitude, and renders a live alignment overlay with a responsive web control panel.

The server runs on port `8000` and is intended for local-network use (for example: `http://polaris.local:8000/`).

---

## Current capabilities

- Live camera capture via `picamera2` + `libcamera`.
- Polaris alignment overlay with:
  - crosshair,
  - polar clock ticks + labels,
  - Polaris marker at computed hour angle,
  - UTC timestamp + Polaris time,
  - optional in-frame luminance histogram.
- Optional constellation overlays around Polaris:
  - Ursa Minor,
  - Camelopardalis,
  - Cassiopeia,
  - Cepheus.
- Image processing controls:
  - live stacking (`alpha` configurable),
  - auto stretch,
  - blackpoint removal,
  - gamma,
  - sigma-k threshold.
- Camera controls:
  - autofocus/manual focus,
  - auto exposure/manual exposure + gain,
  - zoom from `1.0x` to `5.0x` in `0.5` steps.
- Observer/location control:
  - longitude from `-180°` to `+180°`.
- Persistent runtime settings saved to `settings.json`.
- Server-Sent Events (`/events`) to refresh only when a new frame version is available.
- System actions from UI:
  - service restart,
  - Raspberry Pi shutdown.

---

## Project structure

```text
.
├── polaris_finder.py    # Main application: capture loop, rendering, HTTP/SSE API
├── polaris_time.py      # Sidereal time and Polaris hour-angle math
├── constellations.py    # Constellation star catalogs + line segments
├── index.html           # Web UI layout
├── script.js            # UI logic and backend API calls
├── style.css            # Styling (normal and night modes)
├── test.py              # Local helper test script
└── favicon.ico          # Browser icon
```

---

## HTTP endpoints (current)

### Static and stream/image

- `GET /` → UI page (`index.html`)
- `GET /polaris.jpg` → latest rendered JPEG frame
- `GET /events` → SSE stream with frame version updates
- `GET /config` → current runtime configuration (JSON)
- `GET /status` → plain-text diagnostics

### Control endpoints

- `GET /set_zoom?zoom=<float>`
- `GET /set_mode?night=0|1`
- `GET /set_af?af=0|1`
- `GET /set_focus?lens=<float>` or `GET /set_focus?delta=<float>`
- `GET /set_longitude?lon=<float>`
- `GET /set_exposure_mode?ae=0|1`
- `GET /set_camera?exp_ms=<float>&gain=<float>`
- `GET /set_processing?stack=...&stack_alpha=...&stretch=...&blackpoint=...&constellation=...&histogram=...&gamma=...&sigma_k=...`

### System actions

- `POST /restart_system`
- `POST /shutdown_system`

> Note: restart/shutdown routes call privileged shell commands (`sudo systemctl restart ...`, `sudo shutdown -h now`) and require host-side sudo/service setup.

---

## Configuration persistence

Runtime values are loaded from and saved to `settings.json` in the project directory, including:

- night mode,
- autofocus/lens position,
- auto exposure/exposure/gain,
- longitude,
- zoom,
- stacking/stretch parameters,
- constellation + histogram toggles.

---

## Requirements

Typical Raspberry Pi environment:

- Raspberry Pi OS
- Python 3.x
- Pi camera compatible with `picamera2`
- Python packages:
  - `picamera2`
  - `opencv-python`
  - `numpy`

Install dependencies (example):

```bash
python3 -m pip install picamera2 opencv-python numpy
```

---

## Run

From the project directory:

```bash
python3 polaris_finder.py
```

Then open:

```text
http://<raspberry-pi-host-or-ip>:8000/
```

---

## Notes

- The app is designed for practical field alignment rather than full astrometric solving.
- Actual autofocus behavior depends on the camera module and driver support.
- Manual exposure mode uses a frame cadence tied to exposure duration (minimum 1 second loop period).
