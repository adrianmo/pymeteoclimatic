"""Offline contract tests for the Alba parser.

These tests never touch the network and never need a credential. The fixtures are
synthetic: they reproduce the *shape* observed on real stations, including the
full set of 51 ``wxdata`` keys, with placeholder identities and coordinates.
"""

import json
import os
import unittest
from datetime import date, datetime, timedelta, timezone

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


class TestCountsCannotRunBackwards(unittest.TestCase):
    """A negative count is as malformed as a fractional one.

    The earlier fix rejected fractional and non-numeric counts but let a
    negative through, so a station could report minus seven drought days.
    That is the same failure the helper exists to prevent, reached from the
    other side of zero.
    """

    def _with_drought_days(self, value):
        payload = load("currentdata_full.json")
        payload["data"]["wxdata"]["droughtdays"] = value
        return parse_current_data(payload)

    def test_negative_count_is_rejected(self):
        with self.assertRaises(MalformedResponseError) as caught:
            self._with_drought_days(-1)
        self.assertIn("negative", str(caught.exception))

    def test_zero_is_a_legitimate_count(self):
        self.assertEqual(self._with_drought_days(0).precipitation.drought_days, 0)

    def test_positive_count_still_parses(self):
        self.assertEqual(self._with_drought_days(29).precipitation.drought_days, 29)

    def test_negative_station_category_is_reported_absent(self):
        payload = load("currentdata_full.json")
        payload["data"]["mainQuality"] = -3
        self.assertIsNone(parse_current_data(payload).quality.main)


class TestParserFailuresCarryTheResponseStatus(unittest.TestCase):
    """A failure while interpreting a response must report its status.

    The invalid-JSON path was fixed to preserve the status a round earlier,
    but the schema path was not, so two failures on the same 200 response
    reported different metadata depending on which stage rejected it.
    """

    def test_schema_failure_on_a_200_reports_200(self):
        from unittest.mock import patch
        from meteoclimatic.alba import Client

        class _Response:
            headers = {}
            status = 200

            def read(self):
                return b'{"status":200,"data":{}}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with patch("meteoclimatic.alba.client._urlopen",
                   return_value=_Response()):
            with self.assertRaises(MalformedResponseError) as caught:
                Client("dummy-key").get_current_data("AA111")
        self.assertEqual(caught.exception.status, 200)

class TestObservationValidatesWhatExpiryDependsOn(unittest.TestCase):
    """fetched_at and ttl feed expires_at, so both are checked on the way in.

    updated and local_day were validated while these two were not, so a
    naive datetime.now() produced a naive expires_at and the failure only
    surfaced later inside arithmetic, far from the value that caused it.
    """

    def test_naive_fetched_at_is_refused(self):
        from meteoclimatic.alba.models import Observation, Station
        with self.assertRaises(ValueError) as caught:
            Observation(Station("AA111"), fetched_at=datetime.now())
        self.assertIn("aware", str(caught.exception))

    def test_non_datetime_fetched_at_is_refused(self):
        from meteoclimatic.alba.models import Observation, Station
        with self.assertRaises(ValueError):
            Observation(Station("AA111"), fetched_at="now")

    def test_aware_fetched_at_is_accepted(self):
        from meteoclimatic.alba.models import Observation, Station
        observation = Observation(
            Station("AA111"),
            fetched_at=datetime(2026, 8, 19, tzinfo=timezone.utc), ttl=226)
        self.assertIsNotNone(observation.expires_at)
        self.assertIsNotNone(observation.seconds_until_refresh())

    def test_non_numeric_or_negative_ttl_is_refused(self):
        from meteoclimatic.alba.models import Observation, Station
        for bad in ("soon", -5, True):
            with self.subTest(ttl=repr(bad)):
                with self.assertRaises(ValueError):
                    Observation(Station("AA111"), ttl=bad)


class TestUnusableTimezoneIsReportedAbsent(unittest.TestCase):
    """An untrusted zone must never reach ZoneInfo as the wrong type."""

    def test_non_string_timezone_in_the_payload_becomes_none(self):
        payload = load("currentdata_full.json")
        payload["data"]["timezone"] = 12345
        station = parse_current_data(payload).station
        self.assertIsNone(station.timezone)
        self.assertIsNone(station.tzinfo)

    def test_directly_constructed_station_still_returns_none(self):
        from meteoclimatic.alba.models import Station
        self.assertIsNone(Station("AA111", timezone=12345).tzinfo)

    def test_unknown_zone_name_returns_none(self):
        from meteoclimatic.alba.models import Station
        self.assertIsNone(Station("AA111", timezone="Mars/Olympus").tzinfo)

    def test_a_real_zone_still_resolves(self):
        payload = load("currentdata_full.json")
        station = parse_current_data(payload).station
        self.assertEqual(str(station.tzinfo), "Europe/Madrid")

    def test_non_string_name_becomes_none(self):
        payload = load("currentdata_full.json")
        payload["data"]["name"] = 999
        self.assertIsNone(parse_current_data(payload).station.name)

class TestNonFiniteValuesAreMalformed(unittest.TestCase):
    """NaN and Infinity must not survive into a measurement.

    Python's JSON decoder accepts both, so a malformed payload carries them
    straight through. NaN is the dangerous one: every comparison against it
    is false, so the migration comparison helper reported the two transports
    as agreeing on a field where one side was NaN.
    """

    def _with_tmp(self, value):
        payload = load("currentdata_full.json")
        payload["data"]["wxdata"]["TMP"] = value
        return parse_current_data(payload)

    def test_nan_measurement_is_rejected(self):
        with self.assertRaises(MalformedResponseError) as caught:
            self._with_tmp(float("nan"))
        self.assertIn("finite", str(caught.exception))

    def test_infinite_measurement_is_rejected(self):
        for value in (float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(MalformedResponseError):
                    self._with_tmp(value)

    def test_ordinary_measurement_still_parses(self):
        self.assertEqual(self._with_tmp(21.5).temperature.current, 21.5)

    def test_nan_no_longer_reads_as_agreement(self):
        # The reason this matters. Without the guard, comparing 21.5 against
        # NaN reported no difference, because abs(21.5 - nan) > tolerance is
        # false, so the helper that produces migration evidence claimed the
        # two transports matched.
        import math
        self.assertFalse(abs(21.5 - float("nan")) > 0.05)
        with self.assertRaises(MalformedResponseError):
            self._with_tmp(float("nan"))


class TestFalsyOverridesAreRejectedNotReplaced(unittest.TestCase):
    """A falsy invalid override must not become the current time."""

    def test_zero_fetched_at_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_current_data(load("currentdata_full.json"), fetched_at=0)

    def test_empty_string_fetched_at_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_current_data(load("currentdata_full.json"), fetched_at="")

    def test_absent_override_still_defaults(self):
        observation = parse_current_data(load("currentdata_full.json"))
        self.assertIsNotNone(observation.fetched_at.utcoffset())

    def test_an_aware_override_is_used_unchanged(self):
        moment = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        observation = parse_current_data(
            load("currentdata_full.json"), fetched_at=moment)
        self.assertEqual(observation.fetched_at, moment)


class TestUpdatedMustBeAwareOnDirectConstruction(unittest.TestCase):
    """The parser enforced it; direct construction did not."""

    def test_naive_updated_is_rejected(self):
        from meteoclimatic.alba.models import Observation, Station
        with self.assertRaises(ValueError) as caught:
            Observation(Station("AA111"), updated=datetime(2026, 8, 19))
        self.assertIn("aware", str(caught.exception))

    def test_aware_updated_is_accepted(self):
        from meteoclimatic.alba.models import Observation, Station
        moment = datetime(2026, 8, 19, tzinfo=timezone.utc)
        self.assertEqual(
            Observation(Station("AA111"), updated=moment).updated, moment)

    def test_non_finite_ttl_is_rejected(self):
        from meteoclimatic.alba.models import Observation, Station
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(ttl=value):
                with self.assertRaises(ValueError):
                    Observation(Station("AA111"), ttl=value)

    def test_a_finite_ttl_still_yields_an_expiry(self):
        from meteoclimatic.alba.models import Observation, Station
        observation = Observation(
            Station("AA111"),
            fetched_at=datetime(2026, 8, 19, tzinfo=timezone.utc), ttl=226)
        self.assertIsNotNone(observation.expires_at)


class TestLowQualityFlagsAreParsedButNeverFilter(unittest.TestCase):
    """Per-sensor flags are carried and deliberately ignored.

    The provider never defined what ``status`` and ``quality`` mean, and a real
    station was observed reporting ``status=True`` with ``quality=False`` on
    every sensor while returning valid measurements. This fixture encodes the
    adversarial case: every flag is false and the station has no quality
    category, yet the measurements are sound. If a consumer ever filtered on
    these flags, it would blank a perfectly good station, so these tests exist
    to make that regression loud.
    """

    def setUp(self):
        self.observation = parse_current_data(load("currentdata_low_quality.json"))

    def test_station_categories_are_parsed_as_unassigned(self):
        quality = self.observation.quality
        self.assertEqual(quality.main, 0)
        self.assertEqual(quality.additional, 0)
        self.assertEqual(quality.transitional, 0)

    def test_per_sensor_flags_are_parsed_and_reachable(self):
        flags = self.observation.quality.sensors
        self.assertTrue(flags, "per-sensor flags must be carried, not discarded")
        self.assertFalse(flags["TMP"].status)
        self.assertFalse(flags["TMP"].quality)

    def test_every_sensor_reports_unfavourable_flags(self):
        self.assertTrue(
            all(not f.status and not f.quality
                for f in self.observation.quality.sensors.values()),
            "the fixture must keep the adversarial combination",
        )

    def test_measurements_survive_unfavourable_flags(self):
        # The point of the fixture: filtering on the flags would discard all
        # of these, and every one of them is a real reading.
        observation = self.observation
        self.assertIsNotNone(observation.temperature.current)
        self.assertIsNotNone(observation.temperature.daily_max)
        self.assertIsNotNone(observation.temperature.daily_min)
        self.assertIsNotNone(observation.humidity.current)
        self.assertIsNotNone(observation.pressure.current)
        self.assertIsNotNone(observation.wind.speed)
        self.assertIsNotNone(observation.wind.daily_gust)
        self.assertIsNotNone(observation.wind.bearing)
        self.assertIsNotNone(observation.precipitation.daily_total)

    def test_flags_do_not_appear_in_any_availability_decision(self):
        # Availability is decided by the value alone. Same payload, flags
        # flipped to favourable: the parsed measurements must be identical.
        payload = load("currentdata_low_quality.json")
        for key in payload["data"]["sensors"]:
            payload["data"]["sensors"][key]["status"] = True
            payload["data"]["sensors"][key]["quality"] = True
        flipped = parse_current_data(payload)
        self.assertEqual(flipped.temperature.current,
                         self.observation.temperature.current)
        self.assertEqual(flipped.wind.speed, self.observation.wind.speed)
        self.assertEqual(flipped.precipitation.daily_total,
                         self.observation.precipitation.daily_total)


class TestStaleReadingIsDistinguishableFromDueRefresh(unittest.TestCase):
    """Two different things a consumer must not confuse.

    ``updated`` says when the station last produced a reading. ``ttl`` says
    when to ask again. A station that stopped reporting hours ago still
    returns a fresh ttl, so a consumer polling on ttl alone would keep
    re-fetching an old reading and never notice. Both axes are exposed so the
    two cases can be told apart.
    """

    def setUp(self):
        self.fetched_at = datetime(2026, 8, 19, 10, 35, 21, tzinfo=timezone.utc)
        self.observation = parse_current_data(
            load("currentdata_stale.json"), fetched_at=self.fetched_at)

    def test_the_reading_itself_is_old(self):
        age = self.observation.fetched_at - self.observation.updated
        self.assertGreater(age.total_seconds(), 8 * 3600)

    def test_yet_the_next_refresh_is_imminent(self):
        seconds = self.observation.seconds_until_refresh(now=self.fetched_at)
        self.assertGreater(seconds, 0)
        self.assertLessEqual(seconds, 300)

    def test_expiry_is_measured_from_the_fetch_not_from_the_reading(self):
        # If expiry were derived from updated, this reading would already be
        # long expired and a scheduler would hammer the endpoint.
        self.assertEqual(
            self.observation.expires_at,
            self.fetched_at + timedelta(seconds=self.observation.ttl),
        )
        self.assertGreater(self.observation.expires_at, self.fetched_at)

    def test_staleness_is_not_hidden_behind_the_refresh_hint(self):
        # The two are independent: due-for-refresh says nothing about age.
        self.assertLess(self.observation.updated, self.observation.expires_at)
        self.assertLess(self.observation.updated, self.observation.fetched_at)

    def test_measurements_are_still_parsed_for_a_stale_reading(self):
        # Staleness is the consumer's judgement to make; the parser does not
        # blank values or decide on their behalf.
        self.assertIsNotNone(self.observation.temperature.current)
        self.assertIsNotNone(self.observation.local_day)


class TestParityFieldUnits(unittest.TestCase):
    """Pin the unit each parity field is reported in.

    The parser performs no conversion, so these assertions are about what the
    values *mean* rather than about arithmetic. They exist because wind was
    documented as km/h for a time when the service actually reports m/s, and
    nothing in the suite would have caught that: the numbers pass through
    unchanged either way. A consumer that declares the wrong unit
    under-reports wind by a factor of 3.6 with no error.
    """

    def setUp(self):
        self.payload = load("currentdata_full.json")
        self.observation = parse_current_data(self.payload)
        self.wxdata = self.payload["data"]["wxdata"]

    def test_wind_speed_is_metres_per_second_passed_through(self):
        self.assertEqual(self.observation.wind.speed, self.wxdata["WND"])

    def test_daily_gust_is_metres_per_second_passed_through(self):
        self.assertEqual(self.observation.wind.daily_gust, self.wxdata["DGST"])

    def test_no_conversion_is_applied_to_wind(self):
        # Guards against someone "helpfully" converting to km/h in the parser:
        # the boundary that chooses a unit is the consumer, not this library.
        self.assertNotAlmostEqual(
            self.observation.wind.speed, self.wxdata["WND"] * 3.6, places=6)

    def test_remaining_parity_fields_pass_through_unconverted(self):
        for attribute, key in (
            ("temperature.current", "TMP"),
            ("temperature.daily_max", "DHTM"),
            ("temperature.daily_min", "DLTM"),
            ("humidity.current", "HUM"),
            ("humidity.daily_max", "DHHM"),
            ("humidity.daily_min", "DLHM"),
            ("pressure.current", "BAR"),
            ("pressure.daily_max", "DHBR"),
            ("pressure.daily_min", "DLBR"),
            ("wind.bearing", "AZI"),
            ("precipitation.daily_total", "DPCP"),
        ):
            with self.subTest(field=attribute):
                value = self.observation
                for part in attribute.split("."):
                    value = getattr(value, part)
                self.assertEqual(value, self.wxdata[key])


if __name__ == "__main__":
    unittest.main()
