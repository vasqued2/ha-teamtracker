#
# Traverse json and return the value at the end of the chain of keys.
#    json - json to be traversed
#    *keys - list of keys to use to retrieve the value
#    default - default value to be returned if a key is missing
#

async def get_value(json, *keys, default=None):
    v = json
    try:
        for k in keys:
            v = j[k]
        return(v)
    except:
        return(default)


async def get_value2(json, *keys, default=None):
    if len(keys) == 1:
        try:
            return(json[keys[0]])
        except:
            return(default)
    else:
        try:
            return get_value2(json[keys[0]], *keys[1:], default=default)
        except:
            return(default)