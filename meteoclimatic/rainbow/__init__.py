"""Legacy Meteoclimatic RSS transport (Rainbow platform).

.. deprecated::
   Meteoclimatic is migrating to the Alba platform and the RSS feed will be
   retired. Use :mod:`meteoclimatic.alba` instead. This package is removed in
   pymeteoclimatic 1.0, together with its ``lxml`` and ``beautifulsoup4``
   dependencies.

This transport models its own data: ``Observation``, ``Station``, ``Weather`` and
``Condition`` here describe the RSS feed, and are deliberately not shared with
:mod:`meteoclimatic.alba`, which reports different information.
"""

from meteoclimatic.rainbow.weather import Weather, Condition  # noqa: F401
from meteoclimatic.rainbow.station import Station  # noqa: F401
from meteoclimatic.rainbow.observation import Observation  # noqa: F401
from meteoclimatic.rainbow.client import Client  # noqa: F401

__all__ = ["Client", "Observation", "Station", "Weather", "Condition"]
