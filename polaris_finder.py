from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cv2
import math
import time
import threading
from picamera2 import Picamera2 # type: ignore
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from polaris_time import polaris_hour_angle, RA_POLARIS, DEC_POLARIS, lst
import json
import os
import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

log = logging.getLogger("polaris")

settings_lock = threading.Lock()
SETTINGS_FILE = "settings.json"

# Modes: 'SRGGB10_CSI2P' : 1536x864  [120.13 fps - (768, 432)/3072x1728 crop]
#                          2304x1296 [ 56.03 fps - (0, 0)/4608x2592 crop]
#                          4608x2592 [ 14.35 fps - (0, 0)/4608x2592 crop]
WIDTH = 1536
HEIGHT = 864
FPS = 120
CAM_FOCAL = 4.74
PIXEL_SIZE = 1.40
OVERLAY_COLOR = (0, 255, 0)
OVERLAY_COLOR_NIGHT = (0, 0, 255)
OVERLAY_THICKNESS = 1
NUM_TICKS = 72
TICK_LEN = 6
POLARIS_OFFSET_PX = (3600 * (90 - DEC_POLARIS)) / (206 * PIXEL_SIZE / CAM_FOCAL)  # 41px = (3600 * 0.7°) / (206 * 1.40um / 4.74mm)

# Zooms supportés
ZOOM_LEVELS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
JPEG_QUALITY = 90

URSA_MINOR_STARS = {
    "Polaris":  {"ra": RA_POLARIS, "dec": DEC_POLARIS},
    "Yildun":   {"ra": 17.4006, "dec": 86.5592},
    "EpsUMi":   {"ra": 16.7247, "dec": 81.9833},
    "ZetaUMi":  {"ra": 15.7214, "dec": 77.7067},
    "EtaUMi":   {"ra": 16.2808, "dec": 75.6872},
    "Pherkad":  {"ra": 16.3464, "dec": 71.7350},
    "Kochab":   {"ra": 14.8458, "dec": 74.0433},
}   # JNOW Postions
URSA_MINOR_LINES = [ 
    ("Polaris", "Yildun"), 
    ("Yildun", "EpsUMi"), 
    ("EpsUMi", "ZetaUMi"), 
    ("ZetaUMi", "EtaUMi"), 
    ("EtaUMi", "Pherkad"), 
    ("Pherkad", "Kochab"),
    ("Kochab", "ZetaUMi") 
]
CONSTELLATIONS = {
    "ursa_minor" : {"stars": URSA_MINOR_STARS, "lines": URSA_MINOR_LINES},
}

# Cache partagé entre le thread de prod et le serveur HTTP
cache_lock = threading.Lock()
jpeg_cache = None        # {current jpeg_bytes}
last_generated_utc = ""  # info debug éventuelle

# SSE / synchro image
frame_condition = threading.Condition()
frame_version = 0

# Other params to sync
param_lock = threading.Lock()
night_mode_enabled = False
autofocus_enabled = True
lens_position = 0.0
longitude_deg = 0.0
auto_exposure_enabled = True
exposure_time_us = 500000
analogue_gain = 8.0
zoom_level = 1
last_controls = None
live_stacking_enabled = False
auto_stretch_enabled = False
blackpoint_removal_enabled = True
stretch_gamma = 2.2
stretch_sigma_k = 1.8
constellation_enabled = True

# live stacking
stack_lock = threading.Lock()
stack_acc = None

# TOOLS Functions 
def star_to_xy(cx, cy, ra_h, dec_deg, lst_h, zoom_level:float):
    hour_angle_h = (lst_h - ra_h) % 24.0
    angle = 2.0 * math.pi * (hour_angle_h / 24.0)

    distance_deg = 90.0 - dec_deg
    radius_px = round((3600 * distance_deg) / (206 * PIXEL_SIZE / CAM_FOCAL) * zoom_level, 0)

    x = int(cx - radius_px * math.sin(angle))
    y = int(cy - radius_px * math.cos(angle))
    return x, y

def draw_constellation(frame, constellation:str, cx, cy, lst_h, color=(180, 180, 180), thickness:int=1, zoom_level:float=1.0):
    points = {}
    for name, star in CONSTELLATIONS[constellation]['stars'].items():
        x, y = star_to_xy(
            cx, cy,
            star["ra"], star["dec"],
            lst_h,
            zoom_level
        )
        points[name] = (x, y)

    h, w = frame.shape[:2]

    def in_frame(pt):
        x, y = pt
        return -50 <= x < w + 50 and -50 <= y < h + 50

    for a, b in CONSTELLATIONS[constellation]['lines']:
        p1 = points[a]
        p2 = points[b]
        if in_frame(p1) or in_frame(p2):
            cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)

 #   for name, pt in points.items():
 #       if in_frame(pt):
 #           cv2.circle(frame, pt, 2, color, -1, cv2.LINE_AA)

def reset_live_stack():
    global stack_acc

    with stack_lock:
        stack_acc = None

def save_settings():
    with settings_lock:   # 🔒 important
        with param_lock:
            data = {
                "night_mode_enabled": night_mode_enabled,
                "autofocus_enabled": autofocus_enabled,
                "lens_position": lens_position,
                "auto_exposure_enabled": auto_exposure_enabled,
                "exposure_time_us": exposure_time_us,
                "analogue_gain": analogue_gain,
                "longitude_deg": longitude_deg,
                "zoom_level": zoom_level,
                "live_stacking_enabled": live_stacking_enabled,
                "auto_stretch_enabled": auto_stretch_enabled,
                "blackpoint_removal_enabled": blackpoint_removal_enabled,
                "stretch_gamma": stretch_gamma,
                "stretch_sigma_k": stretch_sigma_k,
                "constellation_enabled": constellation_enabled,
            }

        tmp_file = f"{SETTINGS_FILE}.{threading.get_ident()}.tmp"

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        os.replace(tmp_file, SETTINGS_FILE)

def load_settings():
    global night_mode_enabled
    global autofocus_enabled
    global lens_position
    global auto_exposure_enabled
    global exposure_time_us
    global analogue_gain
    global longitude_deg
    global zoom_level
    global live_stacking_enabled
    global auto_stretch_enabled
    global blackpoint_removal_enabled
    global stretch_gamma
    global stretch_sigma_k
    global constellation_enabled

    if not os.path.exists(SETTINGS_FILE):
        return

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        with param_lock:
            night_mode_enabled = bool(data.get("night_mode_enabled", False))
            autofocus_enabled = bool(data.get("autofocus_enabled", True))
            lens_position = float(data.get("lens_position", 0.0))
            auto_exposure_enabled = bool(data.get("auto_exposure_enabled", True))
            exposure_time_us = int(data.get("exposure_time_us", 500000))
            analogue_gain = float(data.get("analogue_gain", 8.0))
            longitude_deg = float(data.get("longitude_deg", 2.0))
            zoom_level = float(data.get("zoom_level", 1.0))
            live_stacking_enabled = bool(data.get("live_stacking_enabled", True))
            auto_stretch_enabled = bool(data.get("auto_stretch_enabled", False))
            blackpoint_removal_enabled = bool(data.get("blackpoint_removal_enabled", True))
            stretch_gamma = float(data.get("stretch_gamma", 2.2))
            stretch_sigma_k = float(data.get("stretch_sigma_k", 1.8))
            constellation_enabled = bool(data.get("constellation_enabled", True))

    except Exception as e:
        log.error(f"Erreur chargement settings: {e}")

def apply_camera_controls():
    global last_controls

    with param_lock:
        current = {
            "af": autofocus_enabled,
            "lp": lens_position,
            "ae": auto_exposure_enabled,
            "exp_us": exposure_time_us,
            "gain": analogue_gain,
        }

    if current != last_controls:
        controls = {}

        if current["af"]:
            controls["AfMode"] = 2
        else:
            controls["AfMode"] = 0
            controls["LensPosition"] = current["lp"]

        if current["ae"]:
            controls["AeEnable"] = True
            controls["FrameDurationLimits"] = (int(1/FPS*1_000_000), int(1/FPS*1_000_000))
        else:
            controls["AeEnable"] = False
            controls["ExposureTime"] = current["exp_us"]
            controls["AnalogueGain"] = current["gain"]
            controls["FrameDurationLimits"] = (current["exp_us"], current["exp_us"])

        try:
            log.info(f"[CAM] apply controls -> {controls}")
            picam2.set_controls(controls)
            last_controls = current
        except Exception as e:
            log.error(f"[CAM] set_controls failed: {e}")

def normalize_zoom(value: float) -> float:
    """Borne et arrondit le zoom au pas de 0.5."""
    value = max(min(ZOOM_LEVELS), min(max(ZOOM_LEVELS), value))
    return round(value * 2) / 2.0


def draw_polar_clock(frame, cx, cy, radius,
                     color=(0, 255, 0),
                     thickness=1,
                     num_ticks=60,
                     rotation_deg=0,
                     polaris_hour=0):
    # Draw clock circle
    cv2.circle(frame, (cx, cy), radius, color, thickness)

    base_thickness = thickness

    for i in range(num_ticks):
        angle_deg = (360.0 * i / num_ticks) + rotation_deg
        angle_rad = math.radians(angle_deg - 90)

        ticks_per_quarter = num_ticks // 4
        ticks_per_30deg = num_ticks // 12

        is_very_major = (i % ticks_per_quarter == 0)
        is_major = (i % ticks_per_30deg == 0)

        if is_very_major:
            tick_len = TICK_LEN * 3
            tick_thickness = base_thickness + 2
        elif is_major:
            tick_len = TICK_LEN * 2
            tick_thickness = base_thickness + 1
        else:
            tick_len = TICK_LEN
            tick_thickness = base_thickness

        x1 = int(cx + (radius - tick_len) * math.cos(angle_rad))
        y1 = int(cy + (radius - tick_len) * math.sin(angle_rad))
        x2 = int(cx + radius * math.cos(angle_rad))
        y2 = int(cy + radius * math.sin(angle_rad))

        cv2.line(frame, (x1, y1), (x2, y2), color, tick_thickness)

    # Draw Polaris
    angle = 2 * math.pi * (polaris_hour / 24.0)
    x_polaris = int(cx - radius * math.sin(angle))
    y_polaris = int(cy - radius * math.cos(angle))
    cv2.circle(frame, (x_polaris, y_polaris), 8, color, 2)

    # Draw clock hours
    labels = {
        "0": 0,
        "18": 90,
        "12": 180,
        "6": 270,
    }

    label_radius = radius + 28

    for text, base_angle in labels.items():
        angle_rad = math.radians(base_angle + rotation_deg - 90)
        tx = int(cx + label_radius * math.cos(angle_rad))
        ty = int(cy + label_radius * math.sin(angle_rad))

        # épaisseur fixe pour les labels
        (tw, th), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1
        )
        org = (tx - tw // 2, ty + th // 2)

        cv2.putText(
            frame,
            text,
            org,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            thickness,
            cv2.LINE_AA
        )


def render_frame_for_zoom(source_frame, zoom=1.0, night_mode=False, polaris_hour=0, constellation_on=True):
    """
    Rend une image finale pour un zoom donné à partir d'une image source déjà capturée.
    """
    frame = source_frame.copy()
    overlay_color = OVERLAY_COLOR_NIGHT if night_mode else OVERLAY_COLOR

    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2

    # ZOOM: crop centré puis resize à la taille d'origine
    if zoom > 1.0:
        crop_w = int(w / zoom)
        crop_h = int(h / zoom)

        x1 = max(0, cx - crop_w // 2)
        y1 = max(0, cy - crop_h // 2)
        x2 = min(w, x1 + crop_w)
        y2 = min(h, y1 + crop_h)

        cropped = frame[y1:y2, x1:x2]
        frame = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        cx, cy = w // 2, h // 2
    
    # draw histogram lower left corner
    hist_img = generate_histogram_image(frame, width=256, height=120)

    hist_h, hist_w = hist_img.shape[:2]
    frame_h, frame_w = frame.shape[:2]

    margin = 20
    x0 = margin
    y0 = frame_h - hist_h - margin

    if x0 >= 0 and y0 >= 0 and x0 + hist_w <= frame_w and y0 + hist_h <= frame_h:
        roi = frame[y0:y0 + hist_h, x0:x0 + hist_w].copy()
        bg = np.full_like(roi, 20)

        blended = cv2.addWeighted(roi, 0.35, bg, 0.65, 0)
        frame[y0:y0 + hist_h, x0:x0 + hist_w] = blended

        mask = hist_img > 0
        frame[y0:y0 + hist_h, x0:x0 + hist_w][mask] = hist_img[mask]

    # Draw horizontal & vertical lines
    cv2.line(frame, (0, cy), (w, cy), overlay_color, OVERLAY_THICKNESS)
    cv2.line(frame, (cx, 0), (cx, h), overlay_color, OVERLAY_THICKNESS)

    # Draw polar circle
    polaris_radius = round(POLARIS_OFFSET_PX * zoom, 0)
    draw_polar_clock(
        frame,
        cx,
        cy,
        polaris_radius,
        color=overlay_color,
        thickness=OVERLAY_THICKNESS,
        num_ticks=NUM_TICKS,
        rotation_deg=0,
        polaris_hour=polaris_hour
    )

    utc_now = datetime.now(timezone.utc)
    if constellation_on:
        draw_constellation(
            frame, 
            "ursa_minor",
            cx, 
            cy, 
            lst(utc_now, longitude_deg), 
            color=overlay_color, 
            thickness=OVERLAY_THICKNESS,
            zoom_level=zoom)

    # Write date/time UTC and Polaris hour
    utc_text = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
    h = int(polaris_hour)
    m = int((polaris_hour - h) * 60)
    utc_text += f" - Polaris: {h:02d}:{m:02d}"

    (font_w, font_h), _ = cv2.getTextSize(
        utc_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2
    )

    margin = 20
    x = w - font_w - margin
    y = margin + font_h

    cv2.putText(
        frame,
        utc_text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        overlay_color,
        OVERLAY_THICKNESS,
        cv2.LINE_AA
    )

    ok, jpg = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    )
    if not ok:
        return None

    return jpg.tobytes()

def publish_new_frame(jpeg_bytes):
    global jpeg_cache, last_generated_utc, frame_version

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    with frame_condition:
        with cache_lock:
            jpeg_cache = jpeg_bytes
            last_generated_utc = generated

        frame_version += 1
        frame_condition.notify_all()

def stretch_blackpoint(frame, gamma=2.2, sigma_k=1.8, remove_black_point=True):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # retrait estimation fond (medianne pour blackpoint) + bruit
    if remove_black_point:
        bp = np.mean(gray)    # Medianne des valeurs --> Principalement du bruit
        sigma = np.std(gray)    # ecart type

        # suppression fond bruité (black point level)
        gray = gray - bp               # possibles valeurs < 0
        gray = np.clip(gray, 0, None)  # bornage Min = 0 pour les valeurs <0, Max = None

        # seuil bruit (après soustraction) sans diminuers les valeurs des étoiles !!!
        threshold = sigma_k * sigma    # on met à zero 2 fois l'écart type,
        gray[gray < threshold] = 0     # normalement les étoiles devraient se situer au dessus car distribution gaussienne etoiles à droite

    # stretching
    # normalisation à valeur de 0-1
    gray = gray / 255

    # Gamma Stretch
    gray = np.power(gray, 1.0 / gamma)    # si gamma >1 alors on éclairci (valeur augmente), si gamma < 1 alors assombri (valeur diminue)
    gray = (gray * 255).astype(np.uint8)  # on revient à une echelle 0-255 pour les pixels

    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) 

def live_stack(frame, alpha=0.8):
    global stack_acc

    with stack_lock:
        frame_f = frame.astype(np.float32)

        if stack_acc is None:
            stack_acc = frame_f
        else:
            stack_acc = alpha * stack_acc + (1.0 - alpha) * frame_f

        return stack_acc.astype(np.uint8)

def generate_histogram_image(frame, width=256, height=150):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # calcul histogramme
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist = hist.flatten()

    # normalisation pour affichage
    hist = hist / hist.max()

    # image noire
    hist_img = np.zeros((height, width, 3), dtype=np.uint8)

    for x in range(256):
        h = int(hist[x] * height)
        cv2.line(hist_img, (x, height), (x, height - h), (255, 255, 255))

    # add line for mean BlackPoint
    bp = int(np.clip(np.mean(gray), 0, 255))
    cv2.line(hist_img, (bp, 0), (bp, height), (0, 0, 255), 1)

    # Petit texte valeur BlackPoint
    cv2.putText(
        hist_img,
        f"{bp}",
        (bp + 3, 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255),
        1,
        cv2.LINE_AA
    )

    return hist_img

def producer_loop():
    """
    Thread de fond:
    - capture une image par seconde au mode expo auto sinon temps d'expo
    - prépare le JPEG avec les paramètres demandés : Zoom, AF, AE, overlay clock+polaris, night mode
    """
    global jpeg_cache, last_generated_utc, auto_stretch, live_stacking

    while True:
        loop_start = time.time()

        with param_lock:
            night_mode = night_mode_enabled
            lon = longitude_deg
            zoom = zoom_level
            ae = auto_exposure_enabled
            stacking_on = live_stacking_enabled
            stretch_on = auto_stretch_enabled
            blackpoint_on = blackpoint_removal_enabled
            gamma = stretch_gamma
            sigma_k = stretch_sigma_k
            constellation_on = constellation_enabled

            if ae:
                frame_period_sec = 1.0
            else:
                frame_period_sec = max(1.0, exposure_time_us / 1_000_000)

            now_utc = datetime.now(timezone.utc)
            polaris_hour = polaris_hour_angle(now_utc, lon)

        # Capture unique pour tous les zooms
        apply_camera_controls()
        try:
            frame = picam2.capture_array()
            # request = picam2.capture_request()
            # metadata = request.get_metadata()
            # frame = request.make_array("main")
            # request.release()
            # print("ExposureTime:", metadata.get("ExposureTime"),"FrameDuration:", metadata.get("FrameDuration"),
            #       "AnalogueGain:", metadata.get("AnalogueGain"), "DigitalGain:", metadata.get("DigitalGain"))
            # flip UpSideDown
            frame = cv2.flip(frame, -1)
            # live stacking
            if stacking_on:
                frame = live_stack(frame, alpha=0.8)
            else:
                reset_live_stack()
            # stretch data
            if stretch_on:
                frame = stretch_blackpoint(frame, gamma=gamma, sigma_k=sigma_k, remove_black_point=blackpoint_on)

        except Exception as e:
            log.error(f"[CAM] Capture error: {e}")

            try:
                picam2.stop()
                time.sleep(1)
                picam2.start()
                time.sleep(1)
                apply_camera_controls()
                continue
            except Exception as e2:
                log.error(f"[CAM] Restart failed: {e2}")
                time.sleep(2)
                continue

        jpeg = render_frame_for_zoom(frame, zoom, night_mode, polaris_hour, constellation_on)
        if jpeg is not None:
            publish_new_frame(jpeg)

        elapsed = time.time() - loop_start
        wait_time = max(0.0, frame_period_sec - elapsed)

        # Attente intelligente
        regen_event.wait(timeout=wait_time)

        # reset du flag
        regen_event.clear()

class Handler(BaseHTTPRequestHandler):
    def send_file(self, filename, content_type):
        try:
            with open(filename, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-type", content_type)
            self.send_header("Content-length", str(len(content)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            error = str(e).encode()
            self.send_response(500)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.send_header("Content-length", str(len(error)))
            self.end_headers()
            try:
                self.wfile.write(error)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def handle_sse(self):
        global frame_version

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        last_seen = -1

        try:
            while True:
                with frame_condition:
                    frame_condition.wait_for(
                        lambda: frame_version != last_seen,
                        timeout=15.0
                    )
                    current_version = frame_version

                if current_version != last_seen:
                    last_seen = current_version
                    payload = (
                        f"id: {current_version}\n"
                        f"event: frame\n"
                        f"data: {json.dumps({'version': current_version})}\n\n"
                    ).encode("utf-8")
                    self.wfile.write(payload)
                    self.wfile.flush()
                else:
                    # keepalive pour éviter qu'un proxy / navigateur coupe la connexion
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()

        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_file("index.html", "text/html; charset=utf-8")

        elif parsed.path == "/style.css":
            self.send_file("style.css", "text/css")

        elif parsed.path == "/script.js":
            self.send_file("script.js", "application/javascript")

        elif parsed.path == "/favicon.ico":
            self.send_file("favicon.ico", "image/x-icon")

        elif parsed.path == "/polaris.jpg":
            with cache_lock:
                img = jpeg_cache

            if img is None:
                self.send_response(503)
                self.send_header("Content-type", "text/plain; charset=utf-8")
                self.end_headers()
                try:
                    self.wfile.write(b"Image not ready yet")
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return

            try:
                self.send_response(200)
                self.send_header("Content-type", "image/jpeg")
                self.send_header("Content-length", str(len(img)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(img)
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif parsed.path == "/events":
            self.handle_sse()

        elif parsed.path == "/set_zoom":
            try:
                zoom = float(params.get("zoom", ["1.0"])[0])
            except ValueError:
                zoom = 1.0

            zoom = normalize_zoom(zoom)

            with param_lock:
                global zoom_level
                zoom_level = zoom

            save_settings()
            regen_event.set()

            self.send_response(204)
            self.end_headers()

        elif parsed.path == "/set_mode":
            night = params.get("night", ["0"])[0] == "1"

            with param_lock:
                global night_mode_enabled
                night_mode_enabled = night

            save_settings()
            regen_event.set()

            self.send_response(204)
            self.end_headers()

        elif parsed.path == "/set_af":
            af = params.get("af", ["1"])[0] == "1"

            with param_lock:
                global autofocus_enabled
                autofocus_enabled = af

            save_settings()
            regen_event.set()

            self.send_response(204)
            self.end_headers()

        elif parsed.path == "/set_focus":
            global lens_position

            with param_lock:
                if "lens" in params:
                    try:
                        lens_position = float(params["lens"][0])
                    except ValueError:
                        pass

                if "delta" in params:
                    try:
                        lens_position += float(params["delta"][0])
                    except ValueError:
                        pass

                lens_position = max(0.0, min(10.0, lens_position))

            save_settings()
            regen_event.set()

            self.send_response(204)
            self.end_headers()

        elif parsed.path == "/set_longitude":
            try:
                lon = float(params.get("lon", ["2.0"])[0])
                lon = max(-180.0, min(180.0, lon))
                with param_lock:
                    global longitude_deg
                    longitude_deg = lon

                save_settings()
                regen_event.set()

                self.send_response(204)
                self.end_headers()

            except ValueError:
                self.send_response(400)
                self.end_headers()

        elif parsed.path == "/set_exposure_mode":
            ae = params.get("ae", ["1"])[0] == "1"

            with param_lock:
                global auto_exposure_enabled
                auto_exposure_enabled = ae

            save_settings()
            regen_event.set()

            self.send_response(204)
            self.end_headers()

        elif parsed.path == "/set_camera":
            try:
                exp_ms = float(params.get("exp_ms", ["500"])[0])
                gain = float(params.get("gain", ["8.0"])[0])

                exp_ms = max(50.0, min(10000.0, exp_ms))
                gain = max(1.0, min(32.0, gain))

                with param_lock:
                    global exposure_time_us, analogue_gain
                    exposure_time_us = int(exp_ms * 1000.0)
                    analogue_gain = gain

                save_settings()
                regen_event.set()

                self.send_response(204)
                self.end_headers()
            except ValueError:
                self.send_response(400)
                self.end_headers()

        elif parsed.path == "/set_processing":
            try:
                with param_lock:
                    global live_stacking_enabled
                    global auto_stretch_enabled
                    global blackpoint_removal_enabled
                    global stretch_gamma
                    global stretch_sigma_k
                    global constellation_enabled

                    if "stack" in params:
                        live_stacking_enabled = params["stack"][0] == "1"

                    if "stretch" in params:
                        auto_stretch_enabled = params["stretch"][0] == "1"

                    if "blackpoint" in params:
                        blackpoint_removal_enabled = params["blackpoint"][0] == "1"

                    if "gamma" in params:
                        stretch_gamma = max(0.1, min(5.0, float(params["gamma"][0])))

                    if "sigma_k" in params:
                        stretch_sigma_k = max(0.0, min(10.0, float(params["sigma_k"][0])))

                    if "constellation" in params:
                        constellation_enabled = params["constellation"][0] == "1"

                reset_live_stack()
                save_settings()
                regen_event.set()

                self.send_response(204)
                self.end_headers()

            except ValueError:
                self.send_response(400)
                self.end_headers()

        elif parsed.path == "/status":
            with cache_lock:
                generated = last_generated_utc
                has_image = jpeg_cache is not None
                image_size = len(jpeg_cache) if jpeg_cache is not None else 0

            with param_lock:
                now_utc = datetime.now(timezone.utc)
                polaris_hour = polaris_hour_angle(now_utc, longitude_deg)
                status_text = (
                    "[generation]\n"
                    f"last_generated_utc={generated}\n"
                    f"has_image={has_image}\n"
                    f"image_size={image_size}\n\n"

                    "[camera]\n"
                    f"autofocus_enabled={autofocus_enabled}\n"
                    f"lens_position={lens_position:.4f}\n"
                    f"auto_exposure_enabled={auto_exposure_enabled}\n"
                    f"exposure_time_us={exposure_time_us}\n"
                    f"exposure_time_ms={exposure_time_us / 1000.0:.1f}\n"
                    f"analogue_gain={analogue_gain:.2f}\n\n"

                    "[site]\n"
                    f"longitude_deg={longitude_deg:.6f}\n\n"

                    "[render]\n"
                    f"night_mode_enabled={night_mode_enabled}\n"
                    f"jpeg_quality={JPEG_QUALITY}\n"
                    f"width={WIDTH}\n"
                    f"height={HEIGHT}\n"
                    f"num_ticks={NUM_TICKS}\n"
                    f"tick_len={TICK_LEN}\n"
                    f"polaris_offset_px={POLARIS_OFFSET_PX}\n"
                    f"polaris_hour={polaris_hour:.4f}\n"
                    f"zoom_levels={ZOOM_LEVELS}\n"
                ).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.send_header("Content-length", str(len(status_text)))
            self.end_headers()
            try:
                self.wfile.write(status_text)
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif parsed.path == "/config":
            with param_lock:
                data = {
                    "night_mode_enabled": night_mode_enabled,
                    "autofocus_enabled": autofocus_enabled,
                    "lens_position": lens_position,
                    "auto_exposure_enabled": auto_exposure_enabled,
                    "exposure_time_us": exposure_time_us,
                    "analogue_gain": analogue_gain,
                    "longitude_deg": longitude_deg,
                    "zoom_level": zoom_level,
                    "live_stacking_enabled": live_stacking_enabled,
                    "auto_stretch_enabled": auto_stretch_enabled,
                    "blackpoint_removal_enabled": blackpoint_removal_enabled,
                    "stretch_gamma": stretch_gamma,
                    "stretch_sigma_k": stretch_sigma_k,
                    "constellation_enabled": constellation_enabled
                }

            payload = json.dumps(data).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        message = format % args
        
        # Filtrage
        if "/polaris.jpg" in message:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [HTTP] {self.address_string()} - {message}")

# MAIN
regen_event = threading.Event()

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
    queue=False,
    buffer_count=1
)
picam2.configure(config)
picam2.start()
time.sleep(2)

load_settings()
apply_camera_controls()

producer_thread = threading.Thread(target=producer_loop, daemon=True)
producer_thread.start()

server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
log.info("Serveur sur http://polaris.local:8000/")
server.serve_forever()
