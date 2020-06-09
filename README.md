# PyMeteoclimatic

A Python wrapper around the Meteoclimatic service.

[![](https://img.shields.io/pypi/v/pymeteoclimatic)](https://pypi.org/project/pymeteoclimatic/)
[![](https://img.shields.io/pypi/pyversions/pymeteoclimatic)](https://pypi.org/project/pymeteoclimatic/)
[![Coverage Status](https://coveralls.io/repos/github/adrianmo/pymeteoclimatic/badge.svg?branch=master)](https://coveralls.io/github/adrianmo/pymeteoclimatic?branch=master)
[![Build & Test](https://github.com/adrianmo/pymeteoclimatic/workflows/Build%20and%20Test/badge.svg)](https://github.com/adrianmo/pymeteoclimatic/actions?query=workflow%3A%22Build+and+Test%22)
[![Publish to Pypi](https://github.com/adrianmo/pymeteoclimatic/workflows/Publish%20to%20Pypi/badge.svg)](https://github.com/adrianmo/pymeteoclimatic/actions?query=workflow%3A%22Publish+to+Pypi%22)

PyMeteoclimatic is a client Python wrapper library for [Meteoclimatic](https://www.meteoclimatic.net). Meteoclimatic is a large network of non-professional automatic real-time weather stations and an important directory of weather resources. The geographical scope of Meteoclimatic comprises the Iberian Peninsula, the two Spanish archipelagos (the Balearic Islands and the Canary Islands), southern France and Africa near the Strait of Gibraltar.

PyMeteoclimatic relies on the [Meteoclimatic RSS feed](https://www.meteoclimatic.net/index/wp/rss_es.html). More specifically, PyMeteoclimatic leverages the coded, normalized data blocks included as HTML comments in the feeds between the `[[<BEGIN:identificador:DATA>]]` and `[[<END:identificador:DATA>]]` tags to obtain station weather information. 


## What data can I get?

With PyMeteoclimatic you can obtain weather information directly from Meteoclimatic stations identified by their code. You can find out the station code from the station profile page in the Meteoclimatic site.

When obtaining the weather information from a station, you will get a `meteoclimatic.Observation` object, which represents the weather which is currently being observed from a certain station and contains the following fields.

| Field | Type | Description |
| --- | --- | --- |
| `reception_time` | `datetime.datetime`     | Timestamp telling when the weather obervation has been received from the station |
| `station`        | `meteoclimatic.Station` | The *Station* relative to this observation |
| `weather`        | `meteoclimatic.Weather` | The *Weather* relative to this observation |

A `meteoclimatic.Station` object contains the following data.

| Field | Type  | Description |
| --- | --- | --- |
| `name` | `str` | Name of the station |
| `code` | `str` | Meteoclimatic code of the station (e.g. "ESCAT4300000043206B") |
| `url`  | `str` | URL of the Meteoclimatic station page |

A `meteoclimatic.Weather` object contains the following data. Note that not all stations have the same physical sensors and capabilities (e.g. pluviometer, barometer, ...), therefore, some of these values may be `None` for some stations. Check the Meteoclimatic station page for more information on your preferred station capabilities.

| Field | Type | Description |
| --- | --- | --- |
| `reference_time`   | `datetime.datetime` | Timestamp of weather measurement |
| `condition`        | `meteoclimatic.Condition` or `str` | Single-word weather condition (e.g. "sun", "suncloud", "rain", ...). If it's a recognized condition, it will be mapped to a value of the `meteoclimatic.Condition` enumerate, otherwise it will be stored as a string |
| `temp_current`     | `float` | Current temperature in Celsius |
| `temp_max`         | `float` | Maximum temperature in Celsius for the past 24 hours |
| `temp_min`         | `float` | Minimum temperature in Celsius for the past 24 hours |
| `humidity_current` | `float` | Current humidity in percentage points |
| `humidity_max`     | `float` | Maximum humidity in percentage points for the past 24 hours |
| `humidity_min`     | `float` | Minimum humidity in percentage points for the past 24 hours |
| `pressure_current` | `float` | Current atmospheric pressure in hPa units |
| `pressure_max`     | `float` | Maximum atmospheric pressure in hPa units for the past 24 hours |
| `pressure_min`     | `float` | Minimum atmospheric pressure in hPa units for the past 24 hours |
| `wind_current`     | `float` | Current wind speed in km/h units |
| `wind_max`         | `float` | Maximum wind speed in km/h units for the past 24 hours |
| `wind_bearing`     | `float` | Wind bearing in degree units |
| `rain`             | `float` | Precipitation in mm units for the past 24 hours |


## Installation

Install with `pip` for your ease.

```
$ pip install pymeteoclimatic
```

## Example

```python
from meteoclimatic import MeteoclimaticClient

client = MeteoclimaticClient()
observation = client.weather_at_station("ESCAT4300000043206B")

print("Timestamp")
print("~~~~~~~~~")
print(observation.reception_time)
print()
print("Station")
print("~~~~~~~")
print(observation.station)
print()
print("Weather")
print("~~~~~~~")
print(observation.weather)
```

Output:

```
Timestamp
~~~~~~~~~
2020-06-09 13:45:55+00:00

Station
~~~~~~~
<class 'meteoclimatic.station.Station'>({'name': 'Reus - Nord (Tarragona)', 'code': 'ESCAT4300000043206B', 'url': 'http://www.meteoclimatic.net/perfil/ESCAT4300000043206B'})

Weather
~~~~~~~
<class 'meteoclimatic.weather.Weather'>({'reference_time': datetime.datetime(2020, 6, 9, 13, 45, 55, tzinfo=datetime.timezone.utc), 'condition': <Condition.sun: 'sun'>, 'temp_current': 24.0, 'temp_max': 24.2, 'temp_min': 13.7, 'humidity_current': 45.0, 'humidity_max': 80.0, 'humidity_min': 44.0, 'pressure_current': 1013.5, 'pressure_max': 1015.3, 'pressure_min': 1013.5, 'wind_current': 13.0, 'wind_max': 31.0, 'wind_bearing': 232.0, 'rain': 0.2})
```

## Contributing

Please feel free to submit issues or fork the repository and send pull requests to update the library and fix bugs, implement support for new sentence types, refactor code, etc.

## License

[MIT License](https://github.com/adrianmo/pymeteoclimatic/blob/master/LICENSE)
