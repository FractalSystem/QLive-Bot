from unidecode import unidecode
import string


# Various utility functions

def sanitise_text(text):
    text = unidecode(text)
    text = text.replace("-", " ")  # eg science-fiction --> science fiction
    text = text.replace("'", " ")
    text = text.replace("|", "I")
    text = text.replace("\n", "")
    text = text.replace("\r", "")
    text = text.replace("  ", " ")
    text = text.replace("   ", " ")
    text = text.replace("_", "")
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text


def sanitise_text_no_lower(text):
    text = unidecode(text)
    text = text.replace("-", " ")  # eg science-fiction --> science fiction
    text = text.replace("\n", "")
    text = text.replace("\r", "")
    text = text.replace("  ", " ")
    text = text.replace("   ", " ")
    text = text.replace("_", "")
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text


def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end
