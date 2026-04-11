from polaris_time import RA_POLARIS, DEC_POLARIS

# JNOW Stars Postions on April 2026
URSA_MINOR_STARS = {
    "Polaris":  {"ra": RA_POLARIS, "dec": DEC_POLARIS},
    "Yildun":   {"ra": 17.4006, "dec": 86.5592},
    "EpsUMi":   {"ra": 16.7247, "dec": 81.9833},
    "ZetaUMi":  {"ra": 15.7214, "dec": 77.7067},
    "EtaUMi":   {"ra": 16.2808, "dec": 75.6872},
    "Pherkad":  {"ra": 15.3464, "dec": 71.7353},
    "Kochab":   {"ra": 14.8458, "dec": 74.0433},
}
CAMELOPARDALIS_STARS = {
    "E634":     {"ra": 5.4481, "dec": 79.2614},
    "yCam":     {"ra": 3.8853, "dec": 71.4142},
    "aCam":     {"ra": 4.9442, "dec": 66.3889},
    "HIP18505": {"ra": 3.9956, "dec": 63.1506},
    "E385":     {"ra": 3.5197, "dec": 60.0328},
}

# Lines to draw from star to star
URSA_MINOR_LINES = [ 
    ("Polaris", "Yildun"), 
    ("Yildun", "EpsUMi"), 
    ("EpsUMi", "ZetaUMi"), 
    ("ZetaUMi", "EtaUMi"), 
    ("EtaUMi", "Pherkad"), 
    ("Pherkad", "Kochab"),
    ("Kochab", "ZetaUMi") 
]
CAMELOPARDALIS_LINES = [
    ("E634", "yCam"), 
    ("yCam", "aCam"), 
    ("aCam", "HP18505"), 
    ("HIP18505", "E385"), 
    ("E385", "yCam") 
]

# array of constellations to draw
CONSTELLATIONS = {
    "ursa_minor" : {"stars": URSA_MINOR_STARS, "lines": URSA_MINOR_LINES},
    "camelopardalis" : {"stars": CAMELOPARDALIS_STARS, "lines": CAMELOPARDALIS_LINES},
}