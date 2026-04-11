# iPolarFinder (Raspberry Pi)

`iPolarFinder` is a lightweight Raspberry Pi project for **polar alignment assistance**.
It captures live frames from a Pi Camera, computes Polaris hour angle from UTC + longitude, and overlays a polar clock (plus optional constellation lines) in a small web UI.

The application is designed to run directly on a Raspberry Pi (typically with Raspberry Pi OS), and expose a local web page at port `8000`.

---

## What the project does

- Captures real-time images from a Raspberry Pi camera (`picamera2`).
- Calculates **Local Sidereal Time (LST)** and **Polaris hour angle**.
- Draws on top of the image:
  - center crosshair,
  - polar clock with ticks and labels,
  - Polaris position marker,
  - optional Ursa Minor constellation segments,
  - mini luminance histogram.
- Provides a web control panel to tune:
  - zoom,
  - night mode,
  - autofocus/manual focus,
  - auto exposure/manual exposure+gain,
  - live stacking,
  - stretch/blackpoint processing,
  - observer longitude.
- Stores runtime settings in `settings.json` so configuration survives restart.

---

## Hardware & software context (RPI)

Typical setup:

- **Board:** Raspberry Pi (e.g. Pi 4 / Pi 5).
- **Camera:** Pi camera compatible with `picamera2` / libcamera.
- **OS:** Raspberry Pi OS.
- **Python:** 3.x.
- **Python packages:** `opencv-python`, `numpy`, `picamera2`.

> Note: camera capture and autofocus controls depend on camera model and libcamera driver support.

---

## File structure

```text
.
├── polaris_finder.py    # Main app: camera, processing thread, HTTP server, API routes
├── polaris_time.py      # Astronomical time helpers (Julian date, GST/LST, Polaris hour angle)
├── constellations.py    # Star coordinates and line definitions used for overlay
├── index.html           # Web UI markup
├── script.js            # Front-end logic + calls to backend endpoints
├── style.css            # UI styles (normal + night mode)
├── test.py              # Small local script to make tests on function
└── favicon.ico          # Browser icon
```

---

## Main functions explained

## `polaris_finder.py`

### Overlay & coordinate helpers

- `star_to_xy(cx, cy, ra_h, dec_deg, lst_h, zoom_level)`
  - Converts a star position (RA/Dec) into pixel coordinates on the frame around the polar center.
- `draw_constellation(frame, constellation, cx, cy, lst_h, ...)`
  - Draws constellation line segments from the catalog in `constellations.py`.
- `draw_polar_clock(frame, cx, cy, radius, ..., polaris_hour)`
  - Draws the polar alignment clock ring, ticks, labels, and Polaris marker.

### Settings & camera controls

- `save_settings()` / `load_settings()`
  - Persist and restore runtime settings from `settings.json`.
- `apply_camera_controls()`
  - Pushes AF/AE/manual lens/exposure/gain controls to `picamera2`.
- `normalize_zoom(value)`
  - Clamps zoom into allowed discrete values (0.5 step).

### Image processing pipeline

- `stretch_blackpoint(frame, gamma, sigma_k, remove_black_point)`
  - Optional grayscale stretch with blackpoint/noise suppression.
- `live_stack(frame, alpha)`
  - Exponential frame stacking to improve visibility/SNR.
- `generate_histogram_image(frame, width, height)`
  - Builds a small histogram image to render inside the frame.
- `render_frame_for_zoom(source_frame, zoom, night_mode, polaris_hour, constellation_on)`
  - Main render stage: crop/resize for zoom, overlays, text timestamp, and JPEG encoding.
- `publish_new_frame(jpeg_bytes)`
  - Updates shared JPEG cache and notifies SSE clients.

### Runtime loop & web server

- `producer_loop()`
  - Background capture/render loop that continuously produces the latest JPEG frame.
- `Handler(BaseHTTPRequestHandler)`
  - Serves static files and JSON/text/image endpoints.
  - Main endpoints include:
    - `GET /` → UI
    - `GET /polaris.jpg` → latest rendered frame
    - `GET /events` → Server-Sent Events (frame version updates)
    - `GET /config` → current configuration JSON
    - `GET /status` → textual diagnostics
    - `GET /set_*` routes for controls (zoom, mode, AF/focus, exposure, processing, longitude)

---

## `polaris_time.py`

- `julian_date(dt)`
  - UTC datetime → Julian Date.
- `gst_from_jd(JD)`
  - Julian Date → Greenwich Sidereal Time (hours).
- `lst_from_gst(gst_hours, longitude_deg)`
  - GST + longitude → Local Sidereal Time (hours).
- `lst(dt_utc, longitude_deg)`
  - Convenience function for LST from UTC datetime.
- `polaris_hour_angle(dt_utc, longitude_deg)`
  - Computes Polaris hour angle in `[0, 24)` hours.
- `dec_to_time(dec_hour)`
  - Decimal hour → `(h, m, s)`.

---

## `constellations.py`

- Defines star coordinates (RA/Dec) for Ursa Minor and line pairs to draw.
- Exposes `CONSTELLATIONS` dictionary consumed by `draw_constellation()`.

---

## `script.js` (front-end)

Main responsibilities:

- Keep UI state in sync (zoom, focus, exposure, processing toggles).
- Call backend endpoints (`/set_zoom`, `/set_mode`, `/set_af`, `/set_focus`, `/set_camera`, `/set_processing`, etc.).
- Subscribe to `/events` (SSE) and refresh the displayed image efficiently.

---

## Run

From the project directory on your Raspberry Pi:

```bash
python3 polaris_finder.py
```

Then open:

```text
http://<raspberry-pi-hostname-or-ip>:8000/
```

If your local DNS is configured like in the source log message, this can be:

```text
http://polaris.local:8000/
```

---

## Notes

- This project is focused on practical field alignment help rather than full astrometry.
- For best results, ensure camera focus and exposure are tuned for your sky brightness and optical setup.
