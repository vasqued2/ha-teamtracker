"""Test for config flow"""
from unittest.mock import patch
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN, CONF_API_LANGUAGE, CONF_RECORD_LAST_UPDATE
from homeassistant import setup
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from tests.const import CONFIG_DATA


async def test_team_from_manual_input(hass):
    """Test the multi-step config flow when team id/abbr is manually input"""
    #
    # Step 1: Initiate the flow
    # Step 2: Choose sport
    # Step 3: Choose league
    # Step 4: Leave Team Search blank
    # Step 5: Input Team Abbreviation
    # Step 6: Input Sensor Name (Do not override default name)
    #

    # Step 1: init flow, expect sport selection form
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: choose sport → expect league selection form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sport_key": "football"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "league"

    # Step 3: choose league → expect team search form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"league_id": "NFL"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "search"

    # Step 4: empty search → expect manual entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search_team": ""}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "manual_team"

    # Step 5: enter Team ID → expect finalize entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"team_id": "SEA"} # Must be the team ID from JSON
    )
    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    # Step 6: Do not enter a sensor name to use default (Final Step)
    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
#                "name": "Override Team Name",    # Use default name
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "NFL - SEA"
        assert result["data"] == {
            "name": "NFL - SEA",
            "league_id": "NFL",
            "team_id": "SEA",
            "league_path": "nfl",
            "sport_path": "football",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1

async def test_team_from_league_list(hass, mock_espn_api):
    """Test the multi-step config flow when team selected from list"""
    #
    # Step 1: Initiate the flow
    # Step 2: Choose sport
    # Step 3: Choose league
    # Step 4: Enter team name to search for
    # Step 5: Select team
    # Step 6: Input Sensor Name (Do not override default name)
    #

    # Step 1: init flow, expect sport selection form
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: choose sport → expect league selection form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sport_key": "football"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "league"

    # Step 3: choose league → expect team search form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"league_id": "NCAAF"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "search"

    # Step 4: Enter search team → expect select team form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search_team": "ohio"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_team"

    # Step 5: Select team → expect finalize entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"team_selection": "195"} # Must be the team ID from test file
    )
    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    # Step 6: Do not enter a sensor name to use default (Final Step)
    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
#                "name": "Override Team Name",    # Use default name
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "NCAAF - Ohio Bobcats"
        
        # Verify the data structure matches NCAAF expectations
        assert result["data"]["league_id"] == "NCAAF"
        assert result["data"]["team_id"] == "195"
        assert result["data"]["conference_id"] == "5" # Conference ID from the test file
        assert result["data"]["league_path"] == "college-football"

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_athlete_from_manual_input(hass):
    """Test the multi-step config flow when athlete name is manually input"""
    #
    # Step 1: Initiate the flow
    # Step 2: Choose sport (golf does not require league selection)
    # Step 3: Input Athelete Name
    # Step 4: Input Sensor Name (Do not override default name)
    #

    # Step 1: init flow, expect sport selection form
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: choose sport → expect manual athlete form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sport_key": "golf"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "manual_athlete"

    # Step 3: input athlete name → expect finalize entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"team_id": "Scheffler"} # Must be the team ID from JSON
    )
    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    # Step 6: Do not enter a sensor name to use default (Final Step)
    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
#                "name": "Override Team Name",    # Use default name
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "PGA - Scheffler"
        assert result["data"] == {
            "name": "PGA - Scheffler",
            "league_id": "PGA",
            "team_id": "Scheffler",
            "league_path": "pga",
            "sport_path": "golf",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_custom_api_team_input(hass):
    """Test the multi-step Custom API config flow when team id/abbr is manually input"""
    #
    # Step 1: Initiate the flow
    # Step 2: Choose "XXX" for Custom API
    # Step 3: Input sport_path and league_path for Custom API
    # Step 4: Leave Team Search blank
    # Step 5: Input Team Abbreviation
    # Step 6: Input Sensor Name (Do not override default name)
    #

    # Step 1: init flow, expect sport selection form
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: choose "XXX"  for Custom API → expect custom_api form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sport_key": "XXX"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "custom_api"

    # Step 3: enter sport_path and league_path → expect team search form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {
                "sport_path": "football",
                "league_path": "nfl",
            },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "search"

    # Step 4: empty search → expect manual entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search_team": ""}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "manual_team"

    # Step 5: enter team ID/abbr → expect finalize entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"team_id": "SEA"} # Must be the team ID from JSON
    )
    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    # Step 6: Do not enter a sensor name to use default (Final Step)
    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
#                "name": "Override Team Name",    # Use default name
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "XXX - SEA"
        assert result["data"] == {
            "name": "XXX - SEA",
            "league_id": "XXX",
            "team_id": "SEA",
            "league_path": "nfl",
            "sport_path": "football",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1

async def test_custom_api_team_list(hass, mock_espn_api):
    """Test the multi-step config flow when team selected from list"""
    #
    # Step 1: Initiate the flow
    # Step 2: Choose "XXX" for Custom API
    # Step 3: Enter sport_path and league_path
    # Step 4: Enter team name to search for
    # Step 5: Select team from list
    # Step 6: Input Sensor Name (Override default team name)
    #

    # Step 1: init flow, expect sport selection form
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Step 2: choose sport → expect custom_api form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"sport_key": "XXX"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "custom_api"

    # Step 3: enter sport_path and league_path → expect team search form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {
                "sport_path": "football",
                "league_path": "college-football",
            },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "search"

    # Step 4: enter team search term → expect select_team entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search_team": "ohio"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "select_team"

    # Step 5: select team from list → expect finalize entry form
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"team_selection": "195"} # Must be the team ID from JSON
    )
    assert result["type"] == "form"
    assert result["step_id"] == "finalize"

    # Step 6: Enter a sensor name to override default (Final Step)
    with patch(
        "custom_components.teamtracker.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Override Sensor Name",    # Override name
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Override Sensor Name"

        # Verify the data structure matches NCAAF expectations
        assert result["data"]["league_id"] == "XXX"
        assert result["data"]["team_id"] == "195"
        assert result["data"]["conference_id"] == "5" # Conference ID from the test file as it should be
        assert result["data"]["league_path"] == "college-football"

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1

async def test_options_flow_init(hass):
    """ Test config flow options """

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="team_tracker",
        data=CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Show Options Flow Form
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "form" == result["type"]
    assert "init" == result["step_id"]
    assert {} == result["errors"]

    # Submit Form with Options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"api_language": "en", "record_last_update": False}
    )

    assert "create_entry" == result["type"]
    assert "" == result["title"]
    assert {CONF_API_LANGUAGE: "en", CONF_RECORD_LAST_UPDATE: False} == result["data"]

    await hass.async_block_till_done()
