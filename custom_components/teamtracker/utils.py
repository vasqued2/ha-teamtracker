""" Miscellaneous Utilities """
import json
import logging
import os
import re

_LOGGER = logging.getLogger(__name__)


#
# get_value()
#   Traverse json and return the value at the end of the chain of keys.
#    json - json to be traversed
#    *keys - list of keys to use to retrieve the value
#    default - default value to be returned if a key is missing
#
def get_value(json_input, *keys, default=None):
    """Traverse the json using keys to return the associated value, or default if invalid keys"""

    j = json_input
    try:
        for k in keys:
            j = j[k]
        return j
    except:
        return default


#
#  has_team()
#
def has_team(data, target_team_id):
    """Search for team in json data"""

    for event in data.get("events", []):
        for comp in event.get("competitions", []):
            for competitor in comp.get("competitors", []):
                if competitor.get("team", {}).get("id") == target_team_id:
                    return True
    return False


#
#  is_integer()
#
def is_integer(val):
    """Check if a value is an integer"""

    try:
        int(val)
        return True
    except ValueError:
        return False


#
#  load_file_overrides()
#
def load_file_overrides(default_file: str, custom_file: str) -> dict:
    """Thread-safe file loading utility."""

    override_data = {}

    if os.path.exists(default_file):
        try:
            with open(default_file, "r", encoding="utf-8") as f:
                override_data = json.load(f)
        except json.JSONDecodeError as err:
            _LOGGER.error(
                "Invalid JSON in %s: %s",
                default_file,
                err,
            )
        except OSError as err:
            _LOGGER.error(
                "Unable to read %s: %s",
                default_file,
                err,
            )

    if os.path.exists(custom_file):
        try:
            with open(custom_file, "r", encoding="utf-8") as f:
                custom_data = json.load(f)
                # Merge logic here...
                override_data.update(custom_data)
        except json.JSONDecodeError as err:
            _LOGGER.error(
                "Invalid JSON in %s: %s",
                custom_file,
                err,
            )
        except OSError as err:
            _LOGGER.error(
                "Unable to read %s: %s",
                custom_file,
                err,
            )

    return override_data


#
#  season_slug_to_name()
#
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
