"""Tests for init."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.teamtracker.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

from tests.const import CONFIG_DATA

@pytest.mark.skip(reason="Temporarily skipping this test")
async def test_setup_entry(
    hass,
):
    """Test settting up entities."""
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

@pytest.mark.skip(reason="Temporarily skipping this test")
async def test_unload_entry(hass):
    """Test unloading entities."""
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

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0

    assert await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


# async def test_import(hass):
#     """Test importing a config."""
#     entry = MockConfigEntry(
#         domain=DOMAIN,
#         title="NFL",
#         data=CONFIG_DATA,
#     )
#     await async_setup_component(hass, "persistent_notification", {})
#     with patch(
#         "custom_components.teamtracker.async_setup_entry",
#         return_value=True,
#     ) as mock_setup_entry:

#         ent_reg = async_get(hass)
#         ent_entry = ent_reg.async_get_or_create(
#             "sensor", DOMAIN, unique_id="replaceable_unique_id", config_entry=entry
#         )
#         entity_id = ent_entry.entity_id
#         entry.add_to_hass(hass)
#         await hass.config_entries.async_setup(entry.entry_id)
#         assert entry.unique_id is None
#         assert ent_reg.async_get(entity_id).unique_id == entry.entry_id
