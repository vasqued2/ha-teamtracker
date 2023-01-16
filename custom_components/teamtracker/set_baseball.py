""" Baseball specific functionality"""

from .utils import async_get_value


async def async_set_baseball_values(
    new_values, event, competition_index, team_index, sensor_name
) -> bool:
    """Set baseball specific values"""

    new_values["clock"] = await async_get_value(
        event, "status", "type", "detail"
    )  # Inning
    if new_values["clock"][:3].lower() in ["bot", "mid"]:
        if new_values["team_homeaway"] in [
            "home"
        ]:  # Home outs, at bat in bottom of inning
            new_values["possession"] = new_values["team_id"]
        else:  # Away outs, at bat in bottom of inning
            new_values["possession"] = new_values["opponent_id"]
    else:
        if new_values["team_homeaway"] in [
            "away"
        ]:  # Away outs, at bat in top of inning
            new_values["possession"] = new_values["team_id"]
        else:  # Home outs, at bat in top of inning
            new_values["possession"] = new_values["opponent_id"]

    new_values["outs"] = await async_get_value(
        event, "competitions", 0, "situation", "outs"
    )
    new_values["balls"] = await async_get_value(
        event, "competitions", 0, "situation", "balls"
    )
    new_values["strikes"] = await async_get_value(
        event, "competitions", 0, "situation", "strikes"
    )
    new_values["on_first"] = await async_get_value(
        event, "competitions", 0, "situation", "onFirst"
    )
    new_values["on_second"] = await async_get_value(
        event, "competitions", 0, "situation", "onSecond"
    )
    new_values["on_third"] = await async_get_value(
        event, "competitions", 0, "situation", "onThird"
    )

    return True
