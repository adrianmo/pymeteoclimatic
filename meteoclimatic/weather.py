"""Deprecated import path for ``meteoclimatic.rainbow.weather``.

.. deprecated::
   The RSS transport moved to :mod:`meteoclimatic.rainbow`. Import from there, or
   from the package root. This compatibility module is removed in
   pymeteoclimatic 1.0.
"""

import warnings

from meteoclimatic.rainbow.weather import Weather, Condition  # noqa: F401

warnings.warn(
    "meteoclimatic.weather moved to meteoclimatic.rainbow.weather and this "
    "compatibility module is removed in pymeteoclimatic 1.0.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Weather", "Condition"]
