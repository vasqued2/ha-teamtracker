from .base_provider import BaseSportProvider

# Import provider classes
from .espn import DATA_PROVIDER_ESPN, EspnProvider
from .espn_all_leagues import DATA_PROVIDER_ESPN_ALL_LEAGUES, EspnAllLeaguesProvider
from .ht import DATA_PROVIDER_HOCKEYTECH, HockeyTechProvider


def get_provider(provider_type: str) -> BaseSportProvider:
    """Factory function to get the correct provider instance."""
    providers = {
        DATA_PROVIDER_ESPN: EspnProvider,
        DATA_PROVIDER_ESPN_ALL_LEAGUES: EspnAllLeaguesProvider,
        DATA_PROVIDER_HOCKEYTECH: HockeyTechProvider,
    }

    provider_class = providers.get(provider_type.lower())

    if not provider_class:
        raise ValueError(f"Unknown provider type: {provider_type}")

    return provider_class()