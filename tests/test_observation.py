import pytest
import os
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from meteoclimatic import Observation, Station, Weather, Condition


class TestObservation:

    _test_dict = {
        'reception_time': datetime(2020, 6, 4, 10, 48,
                                   1, 0, timezone.utc),
        'station': Station(name="Reus - Nord (Tarragona)",
                           code="ESCAT4300000043206B",
                           url="http://www.meteoclimatic.net/perfil/ESCAT4300000043206B"),
        'weather': Weather(reference_time=datetime(2020, 6, 4, 10, 48,
                                                   1, 0, timezone.utc),
                           condition=Condition.hazesun,
                           temp_current=17.6,
                           temp_max=17.9,
                           temp_min=16.0,
                           humidity_current=77.0,
                           humidity_max=96.0,
                           humidity_min=74.0,
                           pressure_current=1002.0,
                           pressure_max=1003.8,
                           pressure_min=1000.9,
                           wind_current=0.0,
                           wind_max=29.0,
                           wind_bearing=300.0,
                           rain=3.2)
    }

    def test_init_ok(self):
        o = Observation(**self._test_dict)
        assert o.reception_time.minute == 48
        assert o.station.code == "ESCAT4300000043206B"
        assert o.weather.pressure_min == 1000.9

    @ pytest.mark.parametrize("field_name,field_value,expected_error", [
        ('reception_time', 123, 'reception_time is not an instance of datetime.datetime'),
        ('station', {"foo": "bar"},
         'station is not an instance of meteoclimatic.Station'),
        ('weather', {"foo": "bar"},
         'weather is not an instance of meteoclimatic.Weather'),
    ])
    def test_init_fails_when_wrong_data_provided(self, field_name, field_value, expected_error):
        d1 = self._test_dict.copy()
        d1[field_name] = field_value
        with pytest.raises(ValueError) as error:
            Observation(**d1)
        assert str(error.value) == expected_error

    @ pytest.mark.parametrize("test_file, expected_result", [
        ("full_station.xml", Observation(
            reception_time=datetime(2020, 6, 4, 10, 48,
                                    1, 0, timezone.utc),
            station=Station(name="Reus - Nord (Tarragona)",
                            code="ESCAT4300000043206B",
                            url="http://www.meteoclimatic.net/perfil/ESCAT4300000043206B"),
            weather=Weather(reference_time=datetime(2020, 6, 4, 10, 48,
                                                    1, 0, timezone.utc),
                            condition=Condition.hazesun,
                            temp_current=17.6,
                            temp_max=17.9,
                            temp_min=16.0,
                            humidity_current=77.0,
                            humidity_max=96.0,
                            humidity_min=74.0,
                            pressure_current=1002.0,
                            pressure_max=1003.8,
                            pressure_min=1000.9,
                            wind_current=0.0,
                            wind_max=29.0,
                            wind_bearing=300.0,
                            rain=3.2)
        )),
        ("thermoeolic_station.xml", Observation(
            reception_time=datetime(2020, 6, 4, 11, 0,
                                    0, 0, timezone.utc),
            station=Station(name="Mompía (Cantabria)",
                            code="ESCTB3900000039108A",
                            url="http://www.meteoclimatic.net/perfil/ESCTB3900000039108A"),
            weather=Weather(reference_time=datetime(2020, 6, 4, 11, 0,
                                                    0, 0, timezone.utc),
                            condition=Condition.hazesun,
                            temp_current=17.7,
                            temp_max=18.9,
                            temp_min=13.8,
                            humidity_current=80.0,
                            humidity_max=96.0,
                            humidity_min=76.0,
                            pressure_current=1009.0,
                            pressure_max=1009.6,
                            pressure_min=1006.4,
                            wind_current=21.0,
                            wind_max=48.0,
                            wind_bearing=292.0,
                            rain=10.6)
        )),
        ("thermometric_station.xml", Observation(
            reception_time=datetime(2020, 6, 4, 10, 39,
                                    0, 0, timezone.utc),
            station=Station(name="Sopeña de Curueño (León)",
                            code="ESCYL2400000024840A",
                            url="http://www.meteoclimatic.net/perfil/ESCYL2400000024840A"),
            weather=Weather(reference_time=datetime(2020, 6, 4, 10, 39,
                                                    0, 0, timezone.utc),
                            condition=Condition.hazesun,
                            temp_current=11.4,
                            temp_max=13.0,
                            temp_min=4.0,
                            humidity_current=76.0,
                            humidity_max=100.0,
                            humidity_min=71.0,
                            pressure_current=1007.9,
                            pressure_max=1007.9,
                            pressure_min=1004.0,
                            wind_current=2.0,
                            wind_max=27.0,
                            wind_bearing=340,
                            rain=0.2)
        )),
        ("thermopluviometric_station.xml", Observation(
            reception_time=datetime(2020, 6, 4, 10, 45,
                                    0, 0, timezone.utc),
            station=Station(name="Zafrilla (La Reclovilla) (Cuenca)",
                            code="ESCLM1600000016317D",
                            url="http://www.meteoclimatic.net/perfil/ESCLM1600000016317D"),
            weather=Weather(reference_time=datetime(2020, 6, 4, 10, 45,
                                                    0, 0, timezone.utc),
                            condition=Condition.rain,
                            temp_current=9.2,
                            temp_max=12.6,
                            temp_min=6.4,
                            humidity_current=89.0,
                            humidity_max=93.0,
                            humidity_min=79.0,
                            pressure_current=1010.3,
                            pressure_max=1013.7,
                            pressure_min=1007.8,
                            wind_current=1.0,
                            wind_max=12.0,
                            wind_bearing=0.0,
                            rain=19.3)
        )),
        ("unrated_station.xml", Observation(
            reception_time=datetime(2020, 6, 4, 10, 45,
                                    0, 0, timezone.utc),
            station=Station(name="Puçol-Ciudad Jardín (Valencia)",
                            code="ESPVA4600000046530D",
                            url="http://www.meteoclimatic.net/perfil/ESPVA4600000046530D"),
            weather=Weather(reference_time=datetime(2020, 6, 4, 10, 45,
                                                    0, 0, timezone.utc),
                            condition=Condition.sun,
                            temp_current=23.1,
                            temp_max=25.4,
                            temp_min=19.6,
                            humidity_current=49.0,
                            humidity_max=85.0,
                            humidity_min=47.0,
                            pressure_current=1002.2,
                            pressure_max=1002.8,
                            pressure_min=999.9,
                            wind_current=None,
                            wind_max=None,
                            wind_bearing=None,
                            rain=0.2)
        ))
    ])
    def test_from_feed_item(self, test_file, expected_result):
        f = open(os.path.join(os.path.dirname(
            __file__), "feeds", test_file))
        soup_page = BeautifulSoup(f, 'xml')
        f.close()
        items = soup_page.findAll("item")
        actual = Observation.from_feed_item(items[0])
        assert actual == expected_result
