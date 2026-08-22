"""Deprecated import path for ``meteoclimatic.rainbow.feed``.

.. deprecated::
   The RSS transport moved to :mod:`meteoclimatic.rainbow`. Import from there, or
   from the package root. This compatibility module is removed in
   pymeteoclimatic 1.0.
"""

import warnings

from meteoclimatic.rainbow.feed import FeedItemHelper  # noqa: F401

warnings.warn(
    "meteoclimatic.feed moved to meteoclimatic.rainbow.feed and this "
    "compatibility module is removed in pymeteoclimatic 1.0.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["FeedItemHelper"]
