import datetime
import pytest
from meteoclimatic import Condition, Weather


class TestWeather:

    _test_dict = {'reference_time': datetime.datetime(2020, 6, 9, 10, 30, 56, tzinfo=datetime.timezone.utc),
                  'condition': Condition.suncloud,
                  'temp_current': 20.9,
                  'temp_max': 21.0,
                  'temp_min': 13.7,
                  'humidity_current': 55.0,
                  'humidity_max': 80.0,
                  'humidity_min': 54.0,
                  'pressure_current': 1015.3,
                  'pressure_max': 1015.3,
                  'pressure_min': 1014.0,
                  'wind_current': 16.0,
                  'wind_max': 31.0,
                  'wind_bearing': 268.0,
                  'rain': 0.2}

    def test_init_ok(self):
        w = Weather(**self._test_dict)
        assert w.wind_current == 16.0
        assert w.condition == Condition.suncloud

    @pytest.mark.parametrize("field_name,field_value,expected_error", [
        ('reference_time', 123, 'reference_time is not an instance of datetime.datetime'),
        ('humidity_current', -1.0, 'humidity must be between 0 and 100'),
        ('humidity_current', 101.0, 'humidity must be between 0 and 100'),
        ('humidity_max', -1.0, 'humidity must be between 0 and 100'),
        ('humidity_max', 101.0, 'humidity must be between 0 and 100'),
        ('humidity_min', -1.0, 'humidity must be between 0 and 100'),
        ('humidity_min', 101.0, 'humidity must be between 0 and 100'),
        ('wind_current', -1.0, 'wind must be greatear than 0'),
        ('wind_max', -1.0, 'wind must be greatear than 0'),
        ('wind_bearing', -0.1, 'wind bearing must be between 0 and 360'),
        ('wind_bearing', 360.1, 'wind bearing must be between 0 and 360'),
        ('rain', -1.0, 'rain must be greatear than 0')
    ])
    def test_init_fails_when_wrong_data_provided(self, field_name, field_value, expected_error):
        d1 = self._test_dict.copy()
        d1[field_name] = field_value
        with pytest.raises(ValueError) as error:
            Weather(**d1)
        assert str(error.value) == expected_error

    def test_init_when_data_fields_are_none(self):
        d1 = self._test_dict.copy()
        for k in d1.keys():
            if k != 'reference_time':
                d1[k] = None
        w = Weather(**d1)
        assert w.wind_bearing is None
