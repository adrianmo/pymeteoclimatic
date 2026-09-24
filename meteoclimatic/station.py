"""Deprecated import path for ``meteoclimatic.rainbow.station``.

.. deprecated::
   The RSS transport moved to :mod:`meteoclimatic.rainbow`. Import from there, or
   from the package root. This compatibility module is removed in
   pymeteoclimatic 1.0.
"""

import warnings

from meteoclimatic.rainbow.station import Station  # noqa: F401

warnings.warn(
    "meteoclimatic.station moved to meteoclimatic.rainbow.station and this "
    "compatibility module is removed in pymeteoclimatic 1.0.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Station"]
