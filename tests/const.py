"""Constants for tests."""

class PlatformConfigType(dict):
    """Wrapper class to be able to add attributes on a dict."""

    def __init__(self, data=None, entry_id=None, **kwargs):
        super().__init__(**kwargs)
        self.data = data
        self.entry_id = entry_id

# Create the mock object
PLATFORM_TEST_DATA = [
    [PlatformConfigType(
        platform='teamtracker',
        league_id="BAD",
        team_id="MIA",
        name="test_tt_all_test03",
        conference_id="9999",
        timeout=1200,
        entry_id={},
        data={}
    ), False],
    [PlatformConfigType(
        platform='teamtracker',
        league_id="XXX",
        team_id="MIA",
        name="test_tt_all_test04",
        conference_id="9999",
        timeout=1200,
        entry_id={},
        data={}
    ), False],
    [PlatformConfigType(
        platform='teamtracker',
        league_id="MLB",
        team_id="MIA",
        name="test_tt_all_test02",
        conference_id="9999",
        timeout=1200,
        entry_id={},
        data={}
    ), True],
    [PlatformConfigType(
        platform='teamtracker',
        league_id="MLB",
        team_id="MIA",
        name="test_tt_all_test01",
        conference_id="9999",
        entry_id={},
        data={}
    ), True],
]

CONFIG_DATA = {
    "league_id": "MLB",
    "team_id": "MIA",
    "name": "test_tt_all_test01",
    "timeout": 120,
    "conference_id": "9999",
}

CONFIG_DATA2 = {
    "league_id": "NCAAF",
    "team_id": "OSU",
    "name": "test_tt_all_test02",
    "timeout": 120,
    "conference_id": "5",
}

CONFIG_DATA3 = {
    "league_id": "XXX",
    "league_path": "all",
    "sport_path": "soccer",
    "team_id": "183",
    "name": "test_tt_all_test99",
    "timeout": 120,
    "conference_id": "9999",
}

CONFIG_DATA4 = {
    "league_id": "XXX",
    "league_path": "all",
    "sport_path": "soccer",
    "team_id": "CLB",
    "name": "test_tt_all_test99",
    "timeout": 120,
    "conference_id": "9999",
}

# Config w/ team_id = integer and NOT_FOUND
CONFIG_DATA5 = {
    "league_id": "NCAAF",
    "team_id": "195",  # Bad Team ID
    "name": "api_error",
    "timeout": 120,
    "conference_id": "15", # Force API, which will fail
}

# Config w/ team_id = integer and NOT_FOUND
CONFIG_DATA6 = {
    "league_id": "NCAAF",
    "team_id": "195",
    "name": "test_tt_all_test99",
    "timeout": 120,
    "conference_id": "9999", # Team 195 will not be found in test data
}

CONFIG_DATA7 = {
    "league_id": "MLB",
    "team_id": "CIN",
    "name": "test_tt_all_test07",
    "timeout": 120,
    "conference_id": "9999",
}

TEST_DATA = [
    {
        "sensor_name": "test_tt_all_test01",
        "sport": "baseball",
        "league": "MLB",
        "team_abbr": "MIA",
        "frozen_time": "2022-09-08T21:45Z",
    },
    {
        "sensor_name": "test_tt_all_test02",
        "sport": "baseball",
        "league": "MLB",
        "team_abbr": "MIL",
        "frozen_time": "2022-09-08T21:10Z",
    },
    {
        "sensor_name": "test_tt_all_test03",
        "sport": "baseball",
        "league": "MLB",
        "team_abbr": "CIN",
        "frozen_time": "2022-09-09T18:20Z",
    },
    {
        "sensor_name": "test_tt_all_test04",
        "sport": "football",
        "league": "NCAAF",
        "team_abbr": "BGSU",
        "frozen_time": "2022-09-10T19:00Z",
    },
    {
        "sensor_name": "test_tt_all_test05",
        "sport": "football",
        "league": "NCAAF",
        "team_abbr": "ALA",
        "frozen_time": "2022-09-10T17:00Z",
    },
    {
        "sensor_name": "test_tt_all_test06",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "BUF",
        "frozen_time": "2022-09-10T00:20Z",
    },
    {
        "sensor_name": "test_tt_all_test07",
        "sport": "soccer",
        "league": "NWSL",
        "team_abbr": "ORL",
        "frozen_time": "2022-09-09T22:00Z",
    },
    {
        "sensor_name": "test_tt_all_test08",
        "sport": "soccer",
        "league": "MLS",
        "team_abbr": "CLB",
        "frozen_time": "2022-09-10T00:30Z",
    },
    {
        "sensor_name": "test_tt_all_test09",
        "sport": "soccer",
        "league": "WC",
        "team_abbr": "ARG",
        "frozen_time": "2022-12-19T15:00Z",
    },
    {
        "sensor_name": "test_tt_all_test10",
        "sport": "basketball",
        "league": "NBA",
        "team_abbr": "DET",
        "frozen_time": "2022-12-20T23:00Z",
    },
    {
        "sensor_name": "test_tt_all_test11",
        "sport": "basketball",
        "league": "NBA",
        "team_abbr": "UTAH",
        "frozen_time": "2022-10-02T23:00Z",
    },
    {
        "sensor_name": "test_tt_all_test12",
        "sport": "basketball",
        "league": "NBA",
        "team_abbr": "CHA",
        "frozen_time": "2022-10-03T17:00Z",
    },
    {
        "sensor_name": "test_tt_all_test13",
        "sport": "hockey",
        "league": "NHL",
        "team_abbr": "WPG",
        "frozen_time": "2022-12-21T00:00Z",
    },
    {
        "sensor_name": "test_tt_all_test14",
        "sport": "hockey",
        "league": "NHL",
        "team_abbr": "NYI",
        "frozen_time": "2022-10-03T00:00Z",
    },
    {
        "sensor_name": "test_tt_all_test15",
        "sport": "hockey",
        "league": "NHL",
        "team_abbr": "CBJ",
        "frozen_time": "2022-10-02T23:00Z",
    },
    {
        "sensor_name": "test_tt_all_test16",
        "sport": "volleyball",
        "league": "NCAAVBW",
        "team_abbr": "2492", #PEPP
        "frozen_time": "2022-09-08T23:00Z",
    },
    {
        "sensor_name": "test_tt_all_test17",
        "sport": "volleyball",
        "league": "NCAAVBW",
        "team_abbr": "MSST",
        "frozen_time": "2022-09-09T00:00Z",
    },
    {
        "sensor_name": "test_tt_all_test18",
        "sport": "volleyball",
        "league": "NCAAVBW",
        "team_abbr": "ARMY",
        "frozen_time": "2022-09-09T21:00Z",
    },
    {
        "sensor_name": "test_tt_all_test19",
        "sport": "tennis",
        "league": "ATP",
        "team_abbr": "STRUFF",
        "frozen_time": "2024-07-29T13:00Z",
    },
    {
        "sensor_name": "test_tt_all_test20",
        "sport": "tennis",
        "league": "WTA",
        "team_abbr": ".*(?:FUCSOVICS|MAROZSAN).*/.*(?:FUCSOVICS|MAROZSAN).*",
        "frozen_time": "2024-07-28T19:50Z",
    },
    {
        "sensor_name": "test_tt_all_test21",
        "sport": "tennis",
        "league": "WTA",
        "team_abbr": "PAOLINI",
        "frozen_time": "2024-07-29T09:00Z",
    },
    {
        "sensor_name": "test_tt_all_test22",
        "sport": "mma",
        "league": "UFC",
        "team_abbr": "STRICKLAND",
        "frozen_time": "2022-12-17T23:00Z",
    },
    {
        "sensor_name": "test_tt_all_test23",
        "sport": "mma",
        "league": "UFC",
        "team_abbr": "CACERES",
        "frozen_time": "2022-12-18T01:00Z",
    },
    {
        "sensor_name": "test_tt_all_test24",
        "sport": "mma",
        "league": "UFC",
        "team_abbr": "FAKHRETDINOV",
        "frozen_time": "2022-12-18T21:00Z",
    },
    {
        "sensor_name": "test_tt_all_test25",
        "sport": "golf",
        "league": "PGA",
        "team_abbr": "CONNERS",
        "frozen_time": "2022-10-13T05:00Z",
    },
    {
        "sensor_name": "test_tt_all_test26",
        "sport": "cricket",
        "league": "XXX",
        "team_abbr": "BH",
        "frozen_time": "2023-01-01T07:15Z",
    },
    {
        "sensor_name": "test_tt_all_test27",
        "sport": "cricket",
        "league": "XXX",
        "team_abbr": "MR",
        "frozen_time": "2023-01-01T03:40Z",
    },
    {
        "sensor_name": "test_tt_all_test28",
        "sport": "cricket",
        "league": "XXX",
        "team_abbr": "IND",
        "frozen_time": "2022-12-23T03:30Z",
    },
    {
        "sensor_name": "test_tt_all_test29",
        "sport": "racing",
        "league": "F1",
        "team_abbr": "SAINTZ",
        "frozen_time": "2023-04-30T10:00Z",
    },
    {
        "sensor_name": "test_tt_all_test30",
        "sport": "racing",
        "league": "F1",
        "team_abbr": "VERSTAPPEN",
        "frozen_time": "2023-04-29T14:30Z",
    },
    {
        "sensor_name": "test_tt_all_test31",
        "sport": "racing",
        "league": "F1",
        "team_abbr": "STROLLZ",
        "frozen_time": "2023-04-29T09:30Z",
    },
]

MULTIGAME_DATA = [
    {
        "sensor_name": "test_tt_all_test01",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "CLE",  #PRE, PRE
        "expected_event_name": "BAL @ CLE"
    },
    {
        "sensor_name": "test_tt_all_test02",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "CIN", # PRE, IN
        "expected_event_name": "PIT @ CIN"
    },
    {
        "sensor_name": "test_tt_all_test03",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "BAL", # PRE, POST
        "expected_event_name": "TB @ BAL"
    },
    {
        "sensor_name": "test_tt_all_test04",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "PIT",  #IN, PRE
        "expected_event_name": "PIT @ CIN"
    },
    {
        "sensor_name": "test_tt_all_test05",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "GB", # IN, IN
        "expected_event_name": "GB @ ATL"
    },
    {
        "sensor_name": "test_tt_all_test06",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "TB", # IN, POST
        "expected_event_name": "TB @ BAL"
    },
    {
        "sensor_name": "test_tt_all_test07",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "NE",  #POST, PRE
        "expected_event_name": "NE @ TB"
    },
    {
        "sensor_name": "test_tt_all_test08",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "JAX", # POST, IN
        "expected_event_name": "JAX @ WSH"
    },
    {
        "sensor_name": "test_tt_all_test09",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "BUF", # POST, POST
        "expected_event_name": "IND @ BUF"
    },
    {
        "sensor_name": "test_tt_all_test10",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "*",  #PRE, PRE
        "expected_event_name": "GB @ ATL"
    },
    {
        "sensor_name": "test_tt_all_test11",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "KNC", # PRE, IN
        "expected_event_name": "KNC @ ARI"
    },
    {
        "sensor_name": "test_tt_all_test12",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "TNT", # PRE, POST
        "expected_event_name": "NYG @ TNT"
    },
    {
        "sensor_name": "test_tt_all_test13",
        "sport": "football",
        "league": "NFL",
        "team_abbr": "NOT_FOUND", # PRE, POST
        "expected_event_name": None
    },
]