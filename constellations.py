from polaris_time import RA_POLARIS, DEC_POLARIS

# JNOW Postions
URSA_MINOR_STARS = {
    "Polaris":  {"ra": RA_POLARIS, "dec": DEC_POLARIS},
    "Yildun":   {"ra": 17.4006, "dec": 86.5592},
    "EpsUMi":   {"ra": 16.7247, "dec": 81.9833},
    "ZetaUMi":  {"ra": 15.7214, "dec": 77.7067},
    "EtaUMi":   {"ra": 16.2808, "dec": 75.6872},
    "Pherkad":  {"ra": 16.3464, "dec": 71.7350},
    "Kochab":   {"ra": 14.8458, "dec": 74.0433},
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

# array of constellations to draw
CONSTELLATIONS = {
    "ursa_minor" : {"stars": URSA_MINOR_STARS, "lines": URSA_MINOR_LINES},
}