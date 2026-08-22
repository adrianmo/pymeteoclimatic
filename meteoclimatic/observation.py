"""Deprecated import path for ``meteoclimatic.rainbow.observation``.

.. deprecated::
   The RSS transport moved to :mod:`meteoclimatic.rainbow`. Import from there, or
   from the package root. This compatibility module is removed in
   pymeteoclimatic 1.0.
"""

import warnings

from meteoclimatic.rainbow.observation import Observation  # noqa: F401

warnings.warn(
    "meteoclimatic.observation moved to meteoclimatic.rainbow.observation and this "
    "compatibility module is removed in pymeteoclimatic 1.0.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Observation"]
