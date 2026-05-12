""" Miscellaneous Utilities """
import logging
import re

_LOGGER = logging.getLogger(__name__)


#
# Traverse json and return the value at the end of the chain of keys.
#    json - json to be traversed
#    *keys - list of keys to use to retrieve the value
#    default - default value to be returned if a key is missing
#
async def async_get_value(json_input, *keys, default=None):
    """Traverse the json using keys to return the associated value, or default if invalid keys"""

    j = json_input
    try:
        for k in keys:
            j = j[k]
        return j
    except:
        return default


def is_integer(val):
    """Check if a value is an integer"""

    try:
        int(val)
        return True
    except ValueError:
        return False


def has_team(data, target_team_id):
    """Search for team in json data"""

    for event in data.get("events", []):
        for comp in event.get("competitions", []):
            for competitor in comp.get("competitors", []):
                if competitor.get("team", {}).get("id") == target_team_id:
                    return True
    return False


def season_slug_to_name(slug: str) -> str:
    """Convert a season slug like '2025-26-english-premier-league' to 'English Premier League'."""
    if not slug:
        return ""
    body = re.sub(r"^\d{4}(-\d{2})?-", "", slug)
    if body == slug:
        return ""
    def _fmt_word(w):
        # Uppercase abbreviations (no vowels, e.g. "mls", "nfl"); title-case real words
        return w.upper() if w.isalpha() and not re.search(r"[aeiou]", w, re.I) else w.title()
    return " ".join(_fmt_word(w) for w in body.split("-"))
