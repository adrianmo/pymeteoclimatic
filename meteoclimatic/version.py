"""Single source of truth for the package version.

Kept in its own module so that transport packages can read it without importing
the package root, which would create a circular import.
"""

__version__ = "0.1.1"
