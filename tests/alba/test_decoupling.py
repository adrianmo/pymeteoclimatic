"""The core must not depend on any third-party package.

pymeteoclimatic is a general-purpose library; Home Assistant is its principal
consumer but not its owner. These tests enforce that separation mechanically, so
a future change cannot quietly reintroduce a hard dependency.

Each test runs in a subprocess with the relevant modules blocked at import time,
which is the only honest way to prove absence of a dependency.
"""

import subprocess
import sys
import textwrap
import unittest

BLOCKER = """
import sys

class _Blocked:
    def __init__(self, names):
        self.names = names
    def find_module(self, fullname, path=None):
        root = fullname.split(".")[0]
        if root in self.names:
            return self
        return None
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in self.names:
            raise ImportError("%s is blocked for this test" % (fullname,))
        return None
    def load_module(self, fullname):
        raise ImportError("%s is blocked for this test" % (fullname,))

sys.meta_path.insert(0, _Blocked({blocked!r}))
"""


def run_isolated(blocked, body):
    """Run *body* in a subprocess where *blocked* packages cannot be imported."""
    script = BLOCKER.format(blocked=set(blocked)) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )


class TestCoreHasNoThirdPartyDependency(unittest.TestCase):

    def test_model_and_parser_import_without_aiohttp_or_bs4(self):
        result = run_isolated(
            {"aiohttp", "bs4", "lxml"},
            """
            from meteoclimatic.alba import parse_current_data
            from meteoclimatic.alba import Observation, Station, Temperature
            print("ok")
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_synchronous_client_works_without_aiohttp(self):
        """The default client is standard library only."""
        result = run_isolated(
            {"aiohttp"},
            """
            from meteoclimatic.alba import Client
            client = Client("dummy-key")
            print(repr(client))
            print("ok")
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)
        self.assertNotIn("dummy-key", result.stdout)

    def test_parsing_works_without_any_optional_package(self):
        result = run_isolated(
            {"aiohttp", "bs4", "lxml"},
            """
            import json, os
            from meteoclimatic.alba import parse_current_data
            path = os.path.join("tests", "alba", "fixtures", "currentdata_full.json")
            with open(path, encoding="utf-8") as handle:
                observation = parse_current_data(json.load(handle))
            assert observation.temperature.current == 21.5
            assert observation.station.timezone == "Europe/Madrid"
            print("ok")
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_async_client_reports_the_missing_extra_clearly(self):
        """Without aiohttp the failure must name the extra, not leak a traceback."""
        result = run_isolated(
            {"aiohttp"},
            """
            try:
                from meteoclimatic.alba import AsyncClient
            except ImportError as error:
                assert "pymeteoclimatic[async]" in str(error), str(error)
                print("ok")
            else:
                print("unexpectedly imported")
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


class TestNoConsumerCoupling(unittest.TestCase):
    """The public surface must not carry another project's conventions."""

    def test_no_home_assistant_naming_on_the_public_api(self):
        from meteoclimatic.alba import Client

        public = [name for name in dir(Client)
                  if not name.startswith("_")]
        self.assertIn("get_current_data", public)
        # `async_` is a Home Assistant convention, not a Python one.
        self.assertEqual(
            [name for name in public if name.startswith("async_")], []
        )

    def test_modules_do_not_document_a_specific_consumer(self):
        import meteoclimatic.alba as api
        import meteoclimatic.alba.client as client
        import meteoclimatic.alba.models as models
        import meteoclimatic.alba.parsing as parsing

        for module in (api, client, models, parsing):
            self.assertNotIn(
                "home assistant", (module.__doc__ or "").lower(),
                "%s docstring mentions a specific consumer" % (module.__name__,),
            )


if __name__ == "__main__":
    unittest.main()


class TestAlbaDoesNotDependOnTheLegacyTransport(unittest.TestCase):
    """Alba must survive the deletion of the RSS transport at 1.0.

    The two transports were separated so that one can be removed without
    touching the other. That guarantee is easy to lose by accident: a single
    import of a legacy base class would make every Alba exception depend on
    a module scheduled for deletion, and nothing else would notice until the
    deletion broke consumers.
    """

    LEGACY_MODULES = (
        "meteoclimatic.exceptions",
        "meteoclimatic.client",
        "meteoclimatic.feed",
        "meteoclimatic.observation",
        "meteoclimatic.station",
        "meteoclimatic.weather",
    )

    def test_no_alba_module_imports_a_legacy_module(self):
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parents[2] / "meteoclimatic" / "alba"
        pattern = re.compile(
            r"^\s*(?:from|import)\s+(meteoclimatic\.[A-Za-z_][A-Za-z0-9_]*)",
            re.M,
        )
        offenders = {}
        for module in sorted(root.glob("*.py")):
            for match in pattern.finditer(module.read_text(encoding="utf-8")):
                name = match.group(1)
                # meteoclimatic.version is shared package metadata, not part
                # of the RSS transport, so it survives the 1.0 removal.
                if name.startswith("meteoclimatic.alba"):
                    continue
                if name == "meteoclimatic.version":
                    continue
                offenders.setdefault(module.name, []).append(name)
        self.assertEqual(
            offenders, {},
            "Alba must not import from the legacy transport; found %r" % (offenders,),
        )

    def test_alba_errors_do_not_inherit_from_the_legacy_base(self):
        from meteoclimatic.exceptions import MeteoclimaticError
        from meteoclimatic.alba import (
            ApiError, AuthenticationError, BadRequestError,
            MalformedResponseError, RateLimitError, StationNotFound,
            TransportError,
        )
        for error in (ApiError, AuthenticationError, BadRequestError,
                      MalformedResponseError, RateLimitError,
                      StationNotFound, TransportError):
            with self.subTest(error=error.__name__):
                self.assertTrue(issubclass(error, ApiError))
                self.assertFalse(issubclass(error, MeteoclimaticError))

    def test_alba_station_not_found_is_not_the_rss_one(self):
        from meteoclimatic.alba import StationNotFound as AlbaNotFound
        from meteoclimatic.exceptions import StationNotFound as RssNotFound
        self.assertIsNot(AlbaNotFound, RssNotFound)
        # The RSS message describes a feed document this transport never
        # fetches, which is why the message is not reused either.
        self.assertNotIn("item", str(AlbaNotFound("AA111")))
        self.assertIn("AA111", str(AlbaNotFound("AA111")))


class TestWildcardImportDoesNotRequireTheOptionalExtra(unittest.TestCase):
    """``import *`` must not drag in the optional HTTP stack.

    Every other test in this module imports explicitly, which is exactly why
    none of them caught this: ``AsyncClient`` was listed in ``__all__``, so a
    wildcard import resolved it through the lazy ``__getattr__`` and raised
    for anyone without the extra. The gap was in the tests as much as in the
    code, so the wildcard form is now covered in its own right.
    """

    def test_async_client_is_not_in_all(self):
        import meteoclimatic.alba as alba
        self.assertNotIn("AsyncClient", alba.__all__)

    def test_wildcard_import_succeeds_without_aiohttp(self):
        result = run_isolated(
            {"aiohttp"},
            """
            namespace = {}
            exec("from meteoclimatic.alba import *", namespace)
            assert "Client" in namespace
            assert "parse_current_data" in namespace
            assert "AsyncClient" not in namespace
            print("ok")
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_every_exported_name_resolves_without_aiohttp(self):
        result = run_isolated(
            {"aiohttp"},
            """
            import meteoclimatic.alba as alba
            for name in alba.__all__:
                assert getattr(alba, name) is not None, name
            print("ok")
            """,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)
