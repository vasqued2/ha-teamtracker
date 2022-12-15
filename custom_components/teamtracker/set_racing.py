import arrow
import logging
from datetime import date, datetime, timedelta

from .const import (
    CONF_CONFERENCE_ID,
    CONF_LEAGUE_ID,
    CONF_LEAGUE_PATH,
    CONF_SPORT_PATH,
    CONF_TIMEOUT,
    CONF_TEAM_ID,
    COORDINATOR,
    DEFAULT_CONFERENCE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_LEAGUE,
    DEFAULT_LOGO,
    DEFAULT_LEAGUE_PATH,
    DEFAULT_PROB,
    DEFAULT_SPORT_PATH,
    DOMAIN,
    ISSUE_URL,
    LEAGUE_LIST,
    PLATFORMS,
    URL_HEAD,
    URL_TAIL,
    USER_AGENT,
    VERSION,
)


_LOGGER = logging.getLogger(__name__)

