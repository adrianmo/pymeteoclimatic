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
