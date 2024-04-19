import os

from hypothesis import HealthCheck, Verbosity, settings

settings.register_profile(
    "ci", max_examples=1000, suppress_health_check=[HealthCheck.too_slow]
)
settings.register_profile("dev", max_examples=50)
settings.register_profile("debug", max_examples=50, verbosity=Verbosity.verbose)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev").lower())
