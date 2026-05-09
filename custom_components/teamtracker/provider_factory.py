from .base_provider import BaseSportProvider

# Import your provider classes
from .espn import EspnProvider
from .ht import HockeyTechProvider

DATA_PROVIDER_ESPN = "espn"
DATA_PROVIDER_HOCKEYTECH = "hockeytech"

def get_provider(provider_type: str) -> BaseSportProvider:
    """Factory function to get the correct provider instance."""
    providers = {
        DATA_PROVIDER_ESPN: EspnProvider,
        DATA_PROVIDER_HOCKEYTECH: HockeyTechProvider,
    }

    provider_class = providers.get(provider_type.lower())

    if not provider_class:
        raise ValueError(f"Unknown provider type: {provider_type}")

    return provider_class()