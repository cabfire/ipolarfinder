from datetime import datetime, timezone
import math

RA_POLARIS = 3.072      #  RA Polaris JNOW - voir autre valeur de 2.9970 ?
DEC_POLARIS = 89.3770   # DEC Polaris JNOW

def julian_date(dt):
    """Convertit une datetime UTC en date julienne"""
    year = dt.year
    month = dt.month
    day = dt.day + (dt.hour + dt.minute/60 + dt.second/3600) / 24

    if month <= 2:
        year -= 1
        month += 12

    A = math.floor(year / 100)
    B = 2 - A + math.floor(A / 4)

    JD = math.floor(365.25 * (year + 4716)) \
       + math.floor(30.6001 * (month + 1)) \
       + day + B - 1524.5

    return JD


def gst_from_jd(JD):
    """Greenwich Sidereal Time en heures"""
    T = (JD - 2451545.0) / 36525.0

    GST = 280.46061837 \
        + 360.98564736629 * (JD - 2451545.0) \
        + 0.000387933 * T**2 \
        - (T**3) / 38710000.0

    GST = GST % 360.0
    return GST / 15.0  # en heures


def lst_from_gst(gst_hours, longitude_deg):
    """Temps sidéral local en heures"""
    return (gst_hours + longitude_deg / 15.0) % 24.0


def lst(dt_utc, longitude_deg):
    JD = julian_date(dt_utc)
    gst = gst_from_jd(JD)
    return lst_from_gst(gst, longitude_deg)


def polaris_hour_angle(dt_utc, longitude_deg):
    """Retourne l'heure Polaris (0–24h)"""
    hour = (lst(dt_utc, longitude_deg) - RA_POLARIS) % 24.0
    return hour


# =========================
# Exemple d'utilisation
# =========================
if __name__ == "__main__":
    now = datetime.now(timezone.utc)

    # Exemple : France (~2° Est)
    longitude = 2.532330

    polaris_hour = polaris_hour_angle(now, longitude)

    h = int(polaris_hour)
    m = int((polaris_hour - h) * 60)

    print(f"Heure Polaris : {h:02d}h{m:02d} ({polaris_hour:.2f} h)")