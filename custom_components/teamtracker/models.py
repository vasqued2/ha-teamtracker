from dataclasses import asdict, dataclass, fields
from typing import Any, Final

MISSING: Final[Any] = object()

@dataclass
class TeamTrackerValues:
    """Schema for all Team Tracker sensor attributes."""
    # Core Metadata
    state: str | None = MISSING
    sport: str | None = MISSING
    sport_path: str | None = MISSING
    league: str | None = MISSING
    league_path: str | None = MISSING
    league_logo: str | None = MISSING
    league_name: str | None = MISSING
    season: str | None = MISSING
    
    # Event Details
    team_abbr: str | None = MISSING
    opponent_abbr: str | None = MISSING
    event_id: str | None = MISSING
    event_name: str | None = MISSING
    event_url: str | None = MISSING
    event_stream: str | None = MISSING
    date: str | None = MISSING
    kickoff_in: str | None = MISSING
    series_summary: str | None = MISSING
    venue: str | None = MISSING
    location: str | None = MISSING
    tv_network: str | None = MISSING
    odds: str | None = MISSING
    overunder: str | None = MISSING

    # Team Data
    team_name: str | None = MISSING
    team_long_name: str | None = MISSING
    team_id: str | None = MISSING
    team_record: str | None = MISSING
    team_rank: str | None = MISSING
    team_conference_id: str | None = MISSING
    team_homeaway: str | None = MISSING
    team_logo: str | None = MISSING
    team_url: str | None = MISSING
    team_stream: str | None = MISSING
    team_colors: list[str] | None = MISSING
    team_score: str | None = MISSING
    team_win_probability: float| None= MISSING
    team_winner: bool | None = MISSING
    team_timeouts: int | None = MISSING

    # Opponent Data
    opponent_name: str | None = MISSING
    opponent_long_name: str | None = MISSING
    opponent_id: str | None = MISSING
    opponent_record: str | None = MISSING
    opponent_rank: str | None = MISSING
    opponent_conference_id: str | None = MISSING
    opponent_homeaway: str | None = MISSING
    opponent_logo: str | None = MISSING
    opponent_url: str | None = MISSING
    opponent_stream: str | None = MISSING
    opponent_colors: list[str] | None = MISSING
    opponent_score: str | None = MISSING
    opponent_win_probability: float | None = MISSING
    opponent_winner: bool | None = MISSING
    opponent_timeouts: int | None = MISSING

    # Timing / Legacy Names
    quarter: str | None = MISSING
    clock: str | None = MISSING
    possession: str | None = MISSING
    last_play: str | None = MISSING
    down_distance_text: str | None = MISSING

    # Baseball Specific
    outs: int | None = MISSING
    balls: int | None = MISSING
    strikes: int | None = MISSING
    on_first: bool | None = MISSING
    on_second: bool | None = MISSING
    on_third: bool | None = MISSING

    # Soccer/Hockey
    team_shots_on_target: int | None = MISSING
    team_total_shots: int | None = MISSING
    opponent_shots_on_target: int | None = MISSING
    opponent_total_shots: int | None = MISSING

    # Volleyball
    team_sets_won: str | None = MISSING
    opponent_sets_won: str | None = MISSING

    # System/API Metadata
    last_update: str | None = MISSING
    api_message: str | None = MISSING
    api_url: str | None = MISSING
    private_fast_refresh: bool = False

    @classmethod
    def from_dict(cls, values_dict: dict[str, Any]) -> "TeamTrackerValues":
        """Initialize dataclass from a dictionary, ignoring extra keys."""
        # Get the names of all valid fields in this dataclass
        valid_fields = {f.name for f in fields(cls)}
        
        # Filter the input dict to only include valid keys
        filtered_dict = {k: v for k, v in values_dict.items() if k in valid_fields}
        
        return cls(**filtered_dict)

    def to_dict(self) -> dict[str, Any]:
            """Convert to dict, but only include fields that were actually set."""
            return {
                k: v for k, v in asdict(self).items() 
                if v is not MISSING
            }

    def to_dict_all_attr(self) -> dict[str, Any]:
        """Convert properties to a dictionary, translating MISSING sentinels to None."""
        # A robust check that traps the sentinel even if it was deep-copied
        return {
            f.name: (
                None 
                if getattr(self, f.name) is MISSING or type(getattr(self, f.name)).__name__ == 'object'
                else getattr(self, f.name)
            )
            for f in fields(self)
        }
