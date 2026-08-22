"""Deprecated import path for ``meteoclimatic.rainbow.client``.

.. deprecated::
   The RSS transport moved to :mod:`meteoclimatic.rainbow` and its client class
   was renamed to ``Client``. ``MeteoclimaticClient`` remains available here and
   at the package root. This compatibility module is removed in
   pymeteoclimatic 1.0.
"""

import warnings

from meteoclimatic.rainbow.client import Client  # noqa: F401

#: Historical name of :class:`meteoclimatic.rainbow.client.Client`.
MeteoclimaticClient = Client

warnings.warn(
    "meteoclimatic.client moved to meteoclimatic.rainbow.client and this "
    "compatibility module is removed in pymeteoclimatic 1.0.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Client", "MeteoclimaticClient"]
