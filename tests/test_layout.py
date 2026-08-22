"""Package layout, deprecation warnings, and backward compatibility.

The RSS transport moved to ``meteoclimatic.rainbow`` and the API v3 transport to
``meteoclimatic.alba``. These tests pin the compatibility promises made for that
move, so a regression is caught rather than discovered by a user.
"""

import importlib
import subprocess
import sys
import textwrap
import unittest
import warnings


def run_isolated(body):
    """Run *body* in a fresh interpreter, returning the completed process."""
    return subprocess.run(
        [sys.executable, "-W", "always::DeprecationWarning", "-c",
         textwrap.dedent(body)],
        capture_output=True,
        text=True,
    )


class TestNewNames(unittest.TestCase):

    def test_client_is_the_alba_client(self):
        """meteoclimatic.Client is new and always means Alba."""
        import meteoclimatic
        from meteoclimatic.alba import Client

        self.assertIs(meteoclimatic.Client, Client)

    def test_transport_packages_expose_their_own_client(self):
        from meteoclimatic.alba import Client as AlbaClient
        from meteoclimatic.rainbow import Client as RainbowClient

        self.assertIsNot(AlbaClient, RainbowClient)

    def test_async_client_is_reachable_from_both_paths(self):
        import meteoclimatic.alba as alba
        from meteoclimatic.alba.async_client import AsyncClient

        self.assertIs(alba.AsyncClient, AsyncClient)


class TestBackwardCompatibility(unittest.TestCase):
    """Existing callers must keep working until 1.0."""

    def test_legacy_client_alias_still_resolves_to_rss(self):
        import meteoclimatic
        from meteoclimatic.rainbow import Client

        self.assertIs(meteoclimatic.MeteoclimaticClient, Client)

    def test_legacy_model_names_still_resolve(self):
        """This is exactly how Home Assistant imports today."""
        result = run_isolated(
            """
            from meteoclimatic import Condition, Observation, Station, Weather
            from meteoclimatic.exceptions import MeteoclimaticError, StationNotFound
            print("ok")
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_importing_model_types_does_not_warn(self):
        """Warning here would be noise: there is no action to take."""
        result = run_isolated(
            """
            import warnings
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                from meteoclimatic import Condition, Observation
            assert not [w for w in caught
                        if issubclass(w.category, DeprecationWarning)], [
                str(w.message) for w in caught]
            print("ok")
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


class TestDeprecationWarnings(unittest.TestCase):

    def test_instantiating_the_rss_client_warns(self):
        from meteoclimatic.rainbow import Client

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Client()
        messages = [str(w.message) for w in caught
                    if issubclass(w.category, DeprecationWarning)]
        self.assertTrue(messages, "instantiating the RSS client must warn")
        self.assertIn("1.0", messages[0])
        self.assertIn("meteoclimatic.alba", messages[0])

    def test_instantiating_the_alba_client_does_not_warn(self):
        from meteoclimatic.alba import Client

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Client("dummy-key")
        self.assertEqual(
            [w for w in caught if issubclass(w.category, DeprecationWarning)], []
        )

    def test_old_submodule_paths_still_work_and_warn(self):
        """`from meteoclimatic.station import Station` must not break."""
        for module, name in (
            ("meteoclimatic.station", "Station"),
            ("meteoclimatic.weather", "Weather"),
            ("meteoclimatic.observation", "Observation"),
            ("meteoclimatic.feed", "FeedItemHelper"),
            ("meteoclimatic.client", "MeteoclimaticClient"),
        ):
            with self.subTest(module=module):
                result = run_isolated(
                    """
                    import warnings
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        import {module}
                        assert hasattr({module}, "{name}")
                    assert [w for w in caught
                            if issubclass(w.category, DeprecationWarning)], (
                        "{module} must warn")
                    print("ok")
                    """.format(module=module, name=name)
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("ok", result.stdout)

    def test_new_paths_do_not_warn_on_import(self):
        result = run_isolated(
            """
            import warnings
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                import meteoclimatic.rainbow.station
                import meteoclimatic.alba.models
            assert not [w for w in caught
                        if issubclass(w.category, DeprecationWarning)], [
                str(w.message) for w in caught]
            print("ok")
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


class TestModelsAreIndependent(unittest.TestCase):
    """The transports must not share a model.

    Rainbow and Alba report different information, so a shared type would
    misrepresent both, and Alba must not depend on a package that is deleted
    in 1.0.
    """

    def test_alba_does_not_reuse_rainbow_types(self):
        import meteoclimatic.alba as alba
        import meteoclimatic.rainbow as rainbow

        self.assertIsNot(alba.Station, rainbow.Station)
        self.assertIsNot(alba.Observation, rainbow.Observation)

    def test_alba_does_not_import_rainbow(self):
        """Alba must not depend on a package that is deleted at 1.0."""
        result = run_isolated(
            """
            import sys
            import meteoclimatic.alba  # noqa: F401
            leaked = [m for m in sys.modules if m.startswith("meteoclimatic.rainbow")]
            assert not leaked, leaked
            print("ok")
            """
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok", result.stdout)


class TestMigrationComparisonHelper(unittest.TestCase):
    """Comparison survives as a test helper, not as public API."""

    @staticmethod
    def _observation(**groups):
        from meteoclimatic.alba import Observation, Station

        return Observation(Station("AA111"), **groups)

    @staticmethod
    def _weather(**values):
        from datetime import datetime, timezone
        from meteoclimatic.rainbow import Weather

        defaults = dict(
            temp_current=None, temp_max=None, temp_min=None,
            humidity_current=None, humidity_max=None, humidity_min=None,
            pressure_current=None, pressure_max=None, pressure_min=None,
            wind_current=None, wind_max=None, wind_bearing=None, rain=None,
        )
        defaults.update(values)
        return Weather(datetime(2026, 8, 19, tzinfo=timezone.utc), None, **defaults)

    def test_helper_is_not_part_of_the_package(self):
        with self.assertRaises(ImportError):
            importlib.import_module("meteoclimatic.compare")

    def test_agreeing_values_report_no_differences(self):
        from tests.compare import compare
        from meteoclimatic.alba import Temperature, Wind

        weather = self._weather(temp_current=21.5, temp_max=27.1, wind_max=24.1)
        observation = self._observation(
            temperature=Temperature(current=21.5, daily_max=27.1),
            wind=Wind(daily_gust=24.1),
        )
        self.assertEqual(compare(weather, observation), {})

    def test_disagreeing_values_are_reported(self):
        from tests.compare import compare
        from meteoclimatic.alba import Temperature

        weather = self._weather(temp_current=21.5)
        observation = self._observation(temperature=Temperature(current=25.0))
        differences = compare(weather, observation)
        self.assertEqual(differences["temp_current"], (21.5, 25.0))

    def test_assumed_pairings_are_declared(self):
        """The RSS wind_max/Alba gust equivalence is assumed, not verified."""
        from tests.compare import ASSUMED_PAIRS, FIELD_PAIRS

        self.assertEqual(FIELD_PAIRS["wind_max"], "wind.daily_gust")
        self.assertIn("wind_max", ASSUMED_PAIRS)


if __name__ == "__main__":
    unittest.main()
