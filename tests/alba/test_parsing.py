"""Offline contract tests for the Alba parser.

These tests never touch the network and never need a credential. The fixtures are
synthetic: they reproduce the *shape* observed on real stations, including the
full set of 51 ``wxdata`` keys, with placeholder identities and coordinates.
"""

import json
import os
import unittest
from datetime import date, datetime, timezone

from meteoclimatic.alba import (
    FIELD_MAP,
    MalformedResponseError,
    Observation,
    Station,
    parse_current_data,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    """Return a decoded fixture."""
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


class TestCoverage(unittest.TestCase):
    """Every value Alba returns must be reachable."""

    def setUp(self):
        self.payload = load("currentdata_full.json")
        self.observation = parse_current_data(self.payload)

    def test_fixture_carries_every_observed_key(self):
        self.assertEqual(len(self.payload["data"]["wxdata"]), 51)

    def test_every_wxdata_key_is_mapped_or_deliberate(self):
        """No key may be silently dropped."""
        mapped = {key for fields in FIELD_MAP.values() for key in fields.values()}
        # Read directly onto the observation rather than into a group.
        elsewhere = {"local_day", "bar_trend", "droughtdays"}
        unmapped = set(self.payload["data"]["wxdata"]) - mapped - elsewhere
        self.assertEqual(unmapped, set(), "unmapped wxdata keys: %s" % (unmapped,))

    def test_no_group_value_is_left_unset(self):
        """With a fully populated station, nothing should stay None."""
        for group in ("temperature", "humidity", "pressure", "wind",
                      "precipitation", "solar", "air_quality"):
            values = getattr(self.observation, group).as_dict()
            missing = [name for name, value in values.items() if value is None]
            self.assertEqual(missing, [], "%s left unset: %s" % (group, missing))

    def test_raw_payload_is_preserved(self):
        """Anything not modelled, and anything added later, stays reachable."""
        self.assertEqual(self.observation.raw["meteor"], "")
        self.assertEqual(self.observation.raw["robertsson"]["A"], 0)
        self.assertIn("ID", self.observation.raw)


class TestGroups(unittest.TestCase):

    def setUp(self):
        self.observation = parse_current_data(
            load("currentdata_full.json"), cache_directive="no-store"
        )

    def test_temperature(self):
        values = self.observation.temperature
        self.assertEqual(values.current, 21.5)
        self.assertEqual(values.daily_max, 27.1)
        self.assertEqual(values.daily_min, 16.3)
        self.assertEqual(values.average, 21.0)
        self.assertEqual(values.delta_3h, 1.2)

    def test_humidity(self):
        values = self.observation.humidity
        self.assertEqual(values.current, 60.0)
        self.assertEqual(values.daily_max, 88.0)
        self.assertEqual(values.daily_min, 41.0)
        self.assertEqual(values.delta_3h, -4.0)

    def test_pressure_including_trend(self):
        values = self.observation.pressure
        self.assertEqual(values.current, 1013.2)
        self.assertEqual(values.daily_max, 1015.0)
        self.assertEqual(values.daily_min, 1011.7)
        self.assertEqual(values.mean_6h, 1013.1)
        self.assertEqual(values.delta_6h, -0.2)
        self.assertEqual(values.trend, "Steady")

    def test_wind(self):
        values = self.observation.wind
        self.assertEqual(values.speed, 5.4)
        self.assertEqual(values.daily_gust, 24.1)
        self.assertEqual(values.bearing, 180.0)
        self.assertEqual(values.average_bearing, 172.0)

    def test_precipitation_including_count(self):
        values = self.observation.precipitation
        self.assertEqual(values.daily_total, 0.0)
        self.assertEqual(values.current, 0.0)
        self.assertEqual(values.intensity_max, 0.0)
        # A count stays an integer rather than becoming a float.
        self.assertEqual(values.drought_days, 29)
        self.assertIsInstance(values.drought_days, int)

    def test_solar(self):
        values = self.observation.solar
        self.assertEqual(values.radiation, 402.0)
        self.assertEqual(values.daily_radiation, 411.0)
        self.assertEqual(values.uv_index, 1.0)
        self.assertEqual(values.daily_uv_index, 6.0)

    def test_air_quality(self):
        values = self.observation.air_quality
        self.assertEqual(values.aqi, 34.0)
        self.assertEqual(values.pm25, 6.8)
        self.assertEqual(values.daily_pm25_max, 13.5)
        self.assertEqual(values.daily_pm25_min, 2.1)
        self.assertEqual(values.average_pm10, 10.8)

    def test_integer_and_float_values_both_become_floats(self):
        """The API returns int or float for the same field; both are numbers."""
        self.assertIsInstance(self.observation.humidity.current, float)
        self.assertIsInstance(self.observation.temperature.current, float)


class TestObservationLevel(unittest.TestCase):

    def setUp(self):
        self.observation = parse_current_data(
            load("currentdata_full.json"), cache_directive="no-store"
        )

    def test_returns_an_observation_with_a_station(self):
        self.assertIsInstance(self.observation, Observation)
        self.assertIsInstance(self.observation.station, Station)

    def test_station_metadata(self):
        station = self.observation.station
        self.assertEqual(station.code, "AA111")
        self.assertEqual(station.timezone, "Europe/Madrid")
        self.assertEqual(str(station.tzinfo), "Europe/Madrid")
        self.assertEqual(station.elevation, 100.0)

    def test_coordinates_are_not_transposed(self):
        """coord_Y is the latitude and coord_X the longitude."""
        station = self.observation.station
        self.assertEqual(station.latitude, 41.0)
        self.assertEqual(station.longitude, 1.0)

    def test_webcam(self):
        webcam = self.observation.station.webcam
        self.assertTrue(webcam.visible)
        self.assertIn("webcam", webcam.url)

    def test_civil_day_and_freshness(self):
        self.assertEqual(self.observation.local_day, date(2026, 8, 19))
        self.assertEqual(self.observation.ttl, 226)
        self.assertEqual(self.observation.cache_directive, "no-store")
        self.assertEqual(
            self.observation.updated.utcoffset().total_seconds(), 2 * 3600
        )

    def test_sun_times(self):
        sun = self.observation.sun
        self.assertEqual(sun.sunrise.hour, 7)
        self.assertEqual(sun.sunset.hour, 20)
        # Day length is a human-readable string, not a number.
        self.assertEqual(sun.day_length, "13 hrs. 40 min.")

    def test_forecast_is_available_but_separate(self):
        self.assertIn("forecast", self.observation.forecast)

    def test_quality_aggregates_are_category_ids(self):
        quality = self.observation.quality
        self.assertEqual(quality.main, 4)
        self.assertEqual(quality.additional, 0)

    def test_sensor_flags_are_carried_but_not_applied(self):
        """quality=False must never suppress a value."""
        flags = self.observation.quality.sensors["TMP"]
        self.assertTrue(flags.status)
        self.assertFalse(flags.quality)
        self.assertEqual(self.observation.temperature.current, 21.5)


class TestConditionIsExplicitlyAbsent(unittest.TestCase):
    """Alba reports no condition, and that must not look like 'not observed'."""

    def setUp(self):
        self.observation = parse_current_data(load("currentdata_full.json"))

    def test_there_is_no_condition_attribute(self):
        self.assertFalse(hasattr(self.observation, "condition"))

    def test_accessing_condition_explains_why_it_is_absent(self):
        with self.assertRaises(AttributeError) as caught:
            self.observation.condition
        message = str(caught.exception)
        self.assertIn("does not report a weather condition", message)
        self.assertIn("RSS", message)

    def test_other_missing_attributes_fail_normally(self):
        with self.assertRaises(AttributeError):
            self.observation.nonexistent


class TestSparseStation(unittest.TestCase):

    def setUp(self):
        self.observation = parse_current_data(load("currentdata_sparse.json"))

    def test_absent_hardware_yields_none_not_zero(self):
        self.assertIsNone(self.observation.air_quality.pm25)
        self.assertIsNone(self.observation.solar.radiation)
        self.assertIsNone(self.observation.humidity.daily_max)
        self.assertIsNone(self.observation.wind.daily_gust)

    def test_real_zero_survives(self):
        self.assertEqual(self.observation.precipitation.daily_total, 0.0)

    def test_present_values_still_parsed(self):
        self.assertEqual(self.observation.temperature.current, 21.5)

    def test_non_peninsular_timezone_and_coordinates(self):
        station = self.observation.station
        self.assertEqual(station.timezone, "Atlantic/Canary")
        self.assertEqual(str(station.tzinfo), "Atlantic/Canary")
        # A negative longitude makes the axis assignment unambiguous.
        self.assertEqual(station.longitude, -16.0)
        self.assertEqual(station.latitude, 28.0)
        self.assertEqual(
            self.observation.updated.utcoffset().total_seconds(), 1 * 3600
        )


class TestMalformedResponses(unittest.TestCase):

    def test_missing_data_object(self):
        with self.assertRaises(MalformedResponseError):
            parse_current_data({"status": 200, "error": False, "message": "OK"})

    def test_missing_station_code(self):
        payload = load("currentdata_full.json")
        del payload["data"]["stationCode"]
        with self.assertRaises(MalformedResponseError):
            parse_current_data(payload)

    def test_non_numeric_measurement_is_not_silently_dropped(self):
        payload = load("currentdata_full.json")
        payload["data"]["wxdata"]["TMP"] = "hot"
        with self.assertRaises(MalformedResponseError):
            parse_current_data(payload)

    def test_unknown_fields_are_ignored_but_kept_in_raw(self):
        payload = load("currentdata_full.json")
        payload["data"]["brand_new_field"] = {"nested": True}
        payload["data"]["wxdata"]["BRAND_NEW"] = 1
        observation = parse_current_data(payload)
        self.assertEqual(observation.temperature.current, 21.5)
        self.assertIn("brand_new_field", observation.raw)


class TestFetchedAt(unittest.TestCase):

    def test_explicit_fetched_at_is_preserved(self):
        moment = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        observation = parse_current_data(
            load("currentdata_full.json"), fetched_at=moment
        )
        self.assertEqual(observation.fetched_at, moment)


if __name__ == "__main__":
    unittest.main()


class TestMalformedDataIsNotMasked(unittest.TestCase):
    """Malformed values must surface, not be quietly made plausible."""

    def test_naive_updated_is_rejected(self):
        payload = load("currentdata_full.json")
        payload["data"]["updated"] = "2026-08-19T12:35:21"
        with self.assertRaises(MalformedResponseError) as caught:
            parse_current_data(payload)
        self.assertIn("offset", str(caught.exception))

    def test_offset_aware_updated_is_accepted(self):
        payload = load("currentdata_full.json")
        observation = parse_current_data(payload)
        self.assertIsNotNone(observation.updated.utcoffset())

    def test_naive_sunrise_is_reported_absent_rather_than_guessed(self):
        payload = load("currentdata_full.json")
        payload["data"]["extra"]["sunrise"] = "2026-08-19T07:09:09"
        observation = parse_current_data(payload)
        self.assertIsNone(observation.sun.sunrise)

    def test_non_integral_count_is_rejected(self):
        payload = load("currentdata_full.json")
        payload["data"]["wxdata"]["droughtdays"] = 29.5
        with self.assertRaises(MalformedResponseError):
            parse_current_data(payload)

    def test_non_numeric_count_is_rejected(self):
        payload = load("currentdata_full.json")
        payload["data"]["wxdata"]["droughtdays"] = "twenty nine"
        with self.assertRaises(MalformedResponseError):
            parse_current_data(payload)

    def test_whole_number_count_still_parses(self):
        payload = load("currentdata_full.json")
        payload["data"]["wxdata"]["droughtdays"] = 29
        observation = parse_current_data(payload)
        self.assertEqual(observation.precipitation.drought_days, 29)



class TestTtlIsADurationNotAnIdentifier(unittest.TestCase):
    """A ttl sent as a float must not silently disable scheduling."""

    def _with_ttl(self, value):
        payload = load("currentdata_full.json")
        payload["data"]["ttl"] = value
        return parse_current_data(payload)

    def test_integer_ttl_is_preserved(self):
        self.assertEqual(self._with_ttl(226).ttl, 226)

    def test_whole_number_float_is_accepted_as_an_integer(self):
        observation = self._with_ttl(226.0)
        self.assertEqual(observation.ttl, 226)
        self.assertIsNotNone(observation.expires_at)
        self.assertIsNotNone(observation.seconds_until_refresh())

    def test_fractional_ttl_is_kept_rather_than_discarded(self):
        self.assertEqual(self._with_ttl(226.5).ttl, 226.5)

    def test_negative_ttl_is_unusable(self):
        self.assertIsNone(self._with_ttl(-5).ttl)

    def test_non_numeric_ttl_is_unusable(self):
        self.assertIsNone(self._with_ttl("soon").ttl)

    def test_boolean_is_not_a_duration(self):
        self.assertIsNone(self._with_ttl(True).ttl)
