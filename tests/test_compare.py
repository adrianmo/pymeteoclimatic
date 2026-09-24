"""Tests for the migration-only comparison helper.

The helper produces the evidence used to decide whether Alba agrees with the
RSS feed, so a fault in it silently corrupts that evidence rather than failing
loudly. The unit mismatch these tests pin was real: Rainbow reports wind in
km/h and Alba reports it in m/s, and an earlier version subtracted the two
directly.
"""

import json
import os
import unittest
from types import SimpleNamespace

from meteoclimatic.alba import parse_current_data

from .compare import ASSUMED_PAIRS, MS_TO_KMH, compare

FIXTURES = os.path.join(os.path.dirname(__file__), "alba", "fixtures")


def alba_observation():
    with open(
        os.path.join(FIXTURES, "currentdata_full.json"), encoding="utf-8"
    ) as handle:
        return parse_current_data(json.load(handle))


class TestWindUnitsAreReconciled(unittest.TestCase):

    def test_equivalent_wind_is_not_reported_as_a_difference(self):
        observation = alba_observation()
        rainbow = SimpleNamespace(
            wind_current=observation.wind.speed * MS_TO_KMH,
            wind_max=observation.wind.daily_gust * MS_TO_KMH,
        )
        differences = compare(rainbow, observation, tolerance=0.05)
        self.assertNotIn("wind_current", differences)
        self.assertNotIn("wind_max", differences)

    def test_numerically_equal_but_physically_different_wind_is_caught(self):
        observation = alba_observation()
        # The pre-fix behaviour treated these as agreeing, because it
        # compared the bare numbers.
        rainbow = SimpleNamespace(wind_current=observation.wind.speed)
        differences = compare(rainbow, observation, tolerance=0.05)
        self.assertIn("wind_current", differences)

    def test_reported_pair_keeps_each_transport_original_value(self):
        observation = alba_observation()
        rainbow = SimpleNamespace(wind_current=observation.wind.speed)
        differences = compare(rainbow, observation, tolerance=0.05)
        rss_value, alba_value = differences["wind_current"]
        self.assertEqual(rss_value, observation.wind.speed)
        self.assertEqual(alba_value, observation.wind.speed)

    def test_non_wind_fields_are_compared_without_conversion(self):
        observation = alba_observation()
        rainbow = SimpleNamespace(temp_current=observation.temperature.current)
        self.assertNotIn("temp_current", compare(rainbow, observation))


class TestAssumedPairsAreDeclared(unittest.TestCase):

    def test_rain_is_declared_as_an_assumption(self):
        # The module documents that the RSS feed never defined its own
        # accumulation window, so the pairing is an assumption and must say so.
        self.assertIn("rain", ASSUMED_PAIRS)

    def test_gust_is_declared_as_an_assumption(self):
        self.assertIn("wind_max", ASSUMED_PAIRS)
