"""A Python library for the Meteoclimatic weather station network.

Two transports are available and are always selected explicitly; the library
never falls back from one to the other.

* :mod:`meteoclimatic.alba` implements the API v3 read path of the Alba platform.
  ``meteoclimatic.Client`` is an alias for its synchronous client.
* :mod:`meteoclimatic.rainbow` implements the legacy RSS feed. It is deprecated
  and removed in 1.0, along with the ``meteoclimatic.MeteoclimaticClient`` alias.

Each transport models its own data, because the two report different
information: the RSS feed provides a weather condition, and Alba provides a
station time zone, a local civil day and station quality categories.
"""

from meteoclimatic.version import __version__  # noqa: F401

__all__ = [
    "Client",
    "MeteoclimaticClient",
    "Observation",
    "Station",
    "Weather",
    "Condition",
]

# Names that resolve lazily, mapped to the module that provides them. Resolving
# on first access keeps the Alba core importable, without third-party imports,
# BeautifulSoup, which the RSS transport requires.
_LAZY = {
    "Client": ("meteoclimatic.alba", "Client"),
    "MeteoclimaticClient": ("meteoclimatic.rainbow", "Client"),
    "Observation": ("meteoclimatic.rainbow", "Observation"),
    "Station": ("meteoclimatic.rainbow", "Station"),
    "Weather": ("meteoclimatic.rainbow", "Weather"),
    "Condition": ("meteoclimatic.rainbow", "Condition"),
}


def __getattr__(name):
    """Resolve the public names lazily.

    ``MeteoclimaticClient`` continues to mean the RSS client, exactly as before,
    so no existing caller changes behavior. It warns when instantiated, and it is
    removed in 1.0 together with the transport it belongs to. ``Client`` is the
    new name and always means the Alba client, so it never changes meaning.

    The RSS model types are re-exported here for backward compatibility and are
    also removed in 1.0.
    """
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    module_name, attribute = target
    from importlib import import_module

    return getattr(import_module(module_name), attribute)


def __dir__():
    """Include the lazily resolved names in ``dir()``."""
    return sorted(set(globals()) | set(__all__))
