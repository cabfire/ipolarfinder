from polaris_time import RA_POLARIS, DEC_POLARIS

# JNOW Stars Positions on April 2026
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

CASSIOPEIA_STARS = {
    "Caph":     {"ra": 0.1760, "dec": 59.2964},  # beta Cas
    "Schedar":  {"ra": 0.7002, "dec": 56.6814},  # alpha Cas
    "GammaCas": {"ra": 0.9719, "dec": 60.8585},  # gamma Cas
    "Ruchbah":  {"ra": 1.4589, "dec": 60.3714},  # delta Cas
    "Segin":    {"ra": 1.9386, "dec": 63.7983},  # epsilon Cas
}

CEPHEUS_STARS = {
    "Alderamin": {"ra": 21.3194, "dec": 62.6913},  # alpha Cep
    "Alfirk":    {"ra": 21.4822, "dec": 70.6703},  # beta Cep
    "Errai":     {"ra": 23.6719, "dec": 77.7769},  # gamma Cep
    "DeltaCep":  {"ra": 22.8428, "dec": 66.3350},  # delta Cep
    "ZetaCep":   {"ra": 22.1956, "dec": 58.3264},  # zeta Cep
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
    ("aCam", "HIP18505"),
    ("HIP18505", "E385"),
    ("E385", "yCam")
]

CASSIOPEIA_LINES = [
    ("Caph", "Schedar"),
    ("Schedar", "GammaCas"),
    ("GammaCas", "Ruchbah"),
    ("Ruchbah", "Segin"),
]

CEPHEUS_LINES = [
    ("Alfirk", "DeltaCep"),
    ("DeltaCep", "ZetaCep"),
    ("ZetaCep", "Alderamin"),
    ("Alderamin", "Alfirk"),
    ("Alfirk", "Errai"),
    ("Errai", "DeltaCep"),
]

# array of constellations to draw
CONSTELLATIONS = {
    "ursa_minor": {"stars": URSA_MINOR_STARS, "lines": URSA_MINOR_LINES},
    "camelopardalis": {"stars": CAMELOPARDALIS_STARS, "lines": CAMELOPARDALIS_LINES},
    "cassiopeia": {"stars": CASSIOPEIA_STARS, "lines": CASSIOPEIA_LINES},
    "cepheus": {"stars": CEPHEUS_STARS, "lines": CEPHEUS_LINES},
}