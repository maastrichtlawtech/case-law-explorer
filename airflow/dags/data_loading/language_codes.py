"""Language-code normalization at source boundaries."""

ISO3_TO_ISO2 = {
    "eng": "en",
    "fre": "fr",  # ISO 639-2/B spelling used by HUDOC
    "fra": "fr",
}


def normalize_language_code(value, default="en"):
    code = str(value or default).strip().lower()
    return ISO3_TO_ISO2.get(code, code)
