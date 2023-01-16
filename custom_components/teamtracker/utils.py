""" Miscellaneous Utilities """

import logging

_LOGGER = logging.getLogger(__name__)


#
# Traverse json and return the value at the end of the chain of keys.
#    json - json to be traversed
#    *keys - list of keys to use to retrieve the value
#    default - default value to be returned if a key is missing
#
async def async_get_value(json, *keys, default=None):
    """Traverse the json using keys to return the associated value, or default if invalid keys"""

    j = json
    try:
        for k in keys:
            j = j[k]
        return j
    except:
        return default
