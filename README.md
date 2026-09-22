# PyMeteoclimatic

A Python client library for the Meteoclimatic weather station network.

[![](https://img.shields.io/pypi/v/pymeteoclimatic)](https://pypi.org/project/pymeteoclimatic/)
[![](https://img.shields.io/pypi/pyversions/pymeteoclimatic)](https://pypi.org/project/pymeteoclimatic/)
[![Coverage Status](https://coveralls.io/repos/github/adrianmo/pymeteoclimatic/badge.svg?branch=master)](https://coveralls.io/github/adrianmo/pymeteoclimatic?branch=master)
[![Build & Test](https://github.com/adrianmo/pymeteoclimatic/workflows/Build%20and%20Test/badge.svg)](https://github.com/adrianmo/pymeteoclimatic/actions?query=workflow%3A%22Build+and+Test%22)
[![Publish to Pypi](https://github.com/adrianmo/pymeteoclimatic/workflows/Publish%20to%20Pypi/badge.svg)](https://github.com/adrianmo/pymeteoclimatic/actions?query=workflow%3A%22Publish+to+Pypi%22)

[Meteoclimatic](https://www.meteoclimatic.net) is a large network of
non-professional automatic real-time weather stations, and an important directory
of weather resources. Its geographical scope covers the Iberian Peninsula, the two
Spanish archipelagos (the Balearic and the Canary Islands), southern France and
the part of Africa near the Strait of Gibraltar.

---

## Meteoclimatic has two platforms: Rainbow and Alba

This is the single most important thing to understand before using this library,
because it decides which client you need.

**Rainbow** is the original Meteoclimatic platform, the one behind
`www.meteoclimatic.net`. Weather data is published as an **RSS feed**, and
stations are identified by a long code such as `ESCAT4300000043206B`. No
authentication is needed.

**Alba** is the new platform Meteoclimatic is migrating to. It provides a proper
**JSON API (API v3)**, stations are identified by a short code such as `T415`, and
requests are **authenticated with an API key**.

Meteoclimatic is moving every station from Rainbow to Alba. During the transition
both platforms run side by side, and eventually Rainbow and its RSS feed will be
retired.

This library gives you one client per platform, and the platform names are used
throughout so it is always obvious which one you are talking to:

| Platform | Module | Data source | Station code | Authentication | Status |
| --- | --- | --- | --- | --- | --- |
| **Alba** | `meteoclimatic.alba` | API v3 (JSON) | short, e.g. `T415` | API key **required** | Supported |
| **Rainbow** | `meteoclimatic.rainbow` | RSS feed | long, e.g. `ESCAT4300000043206B` | none | **Deprecated**, removed in 1.0 |

### Which one should I use?

**Use Alba.** It is the platform Meteoclimatic is moving to, and the RSS feed will
stop working at some point.

Use Rainbow only if you have not obtained an API key yet, or if your station has
not been migrated. Be aware that it is deprecated: the whole
`meteoclimatic.rainbow` package is removed in version 1.0.

You always choose the platform explicitly. This library never silently falls back
from one to the other, so a failure is always reported rather than hidden behind
data from somewhere else.

---

## Installation

```
$ pip install pymeteoclimatic
```

The Alba model, parser and synchronous client use only the Python standard
library. If you want the asynchronous client, install the optional extra:

```
$ pip install pymeteoclimatic[async]
```

## Quick start (Alba)

```python
from meteoclimatic import Client

client = Client(api_key)
observation = client.get_current_data("T415")

print(observation.station.name)
print(observation.temperature.current)     # 21.5
print(observation.temperature.daily_max)   # 27.1
print(observation.station.timezone)        # 'Europe/Madrid'
print(observation.local_day)               # datetime.date(2026, 8, 19)
```

`meteoclimatic.Client` is the Alba client. You can also import it explicitly as
`meteoclimatic.alba.Client`; they are the same class.

## Authentication

Alba requires the **API Identifier** shown in your Meteoclimatic profile
("Identificador de API"). This is *not* the separate "Key" field on the same page,
which the API rejects with a `401`.

The key belongs to a user rather than to a station, and it can read any public
station, including ones you do not own. Both Alba endpoints used by this library
require it.

The key is sent only as a request header. It is never put in a URL or query
string, never written to a log, and never appears in `repr()` or in an exception,
so it cannot leak through shell history, proxy logs or error reports.

Read it from the environment rather than hard-coding it:

```python
import os
from meteoclimatic import Client

client = Client(os.environ["METEOCLIMATIC_API_KEY"])
```

## Station codes on the two platforms

The move from Rainbow to Alba changed how stations are identified:

| Platform | Example |
| --- | --- |
| Alba (new) | `T415` |
| Rainbow (legacy) | `ESCAT4300000043206B` |

Your station's Alba code is shown on its page on the Meteoclimatic site. An
unknown or invalid code raises `StationNotFound`.

> **Keep your own identifier.** If your application stores data keyed by station,
> keep using the identifier you already have and treat the Alba code as an extra
> attribute. Re-keying your storage on the new code would break history that is
> keyed on the old one.

## What you get

`get_current_data()` returns an `Observation`. Measurements are grouped by
family, and **every value Alba returns is covered**:

```python
observation.temperature.daily_max      # 27.1
observation.wind.daily_gust            # 24.1
observation.precipitation.daily_total  # 0.0
observation.air_quality.pm25           # 6.8
```

| Attribute | Description |
| --- | --- |
| `station` | Code, legacy code, name, time zone, coordinates, webcam |
| `temperature`, `humidity`, `pressure`, `wind`, `precipitation`, `solar`, `air_quality` | The measurement groups |
| `updated` | The station's observation timestamp, with an explicit UTC offset |
| `local_day` | The station's local civil day |
| `ttl` | Seconds approximating the next update |
| `quality` | Station quality categories and per-sensor flags |
| `sun` | Sunrise, sunset and day length |
| `forecast` | The provider's forecast text |
| `raw` | The untouched payload |

### Naming rules

Three rules make the period of every value explicit, which is the usual source
of confusion in weather data:

- a **`daily_`** prefix means the station's local civil day, resetting at local
  midnight — `temperature.daily_max`, `precipitation.daily_total`;
- **`average`** (or `average_<quantity>`) is a mean whose period Meteoclimatic
  has not confirmed; and
- **no period in the name means the period is not known**, not that the value is
  current.

### The measurement groups

| Group | Fields | Unit |
| --- | --- | --- |
| `temperature` | `current`, `daily_max`, `daily_min`, `average`, `delta_3h` | °C |
| `humidity` | `current`, `daily_max`, `daily_min`, `average`, `delta_3h` | % |
| `pressure` | `current`, `daily_max`, `daily_min`, `average`, `mean_6h`, `delta_3h`, `delta_6h`, `trend` | hPa |
| `wind` | `speed`, `daily_gust`, `bearing`, `average_speed`, `average_bearing` | m/s, degrees |
| `precipitation` | `daily_total`, `current`, `average`, `intensity_max`, `drought_days` | mm |
| `solar` | `radiation`, `daily_radiation`, `average_radiation`, `uv_index`, `daily_uv_index`, `average_uv_index` | W/m², index |
| `air_quality` | `aqi`, `pm1`, `pm10`, `pm25`, plus `daily_*_max`, `daily_*_min` and `average_*` | µg/m³ |

`pressure.trend` is one of `Steady`, `Rising`, `Rising Quickly`, `Falling` or
`Falling Quickly`. The `aqi` scale is still being defined by Meteoclimatic.

Wind speed and gust are metres per second. The library performs no
conversion, so a consumer that presents kilometres per hour must convert; in
Home Assistant this is handled by declaring the native unit and letting its
unit system convert for display.

Not every station has every sensor. A value the station does not provide is
`None`. **`None` never means zero**, and a real zero is preserved:

```python
observation.precipitation.daily_total  # 0.0  - it did not rain
observation.air_quality.pm25           # None - this station has no PM sensor
```

**Alba does not report a weather condition.** There is no `condition` attribute;
accessing one raises an `AttributeError` that says so. This is deliberate:
reporting `None` would be indistinguishable from a condition that was simply not
observed, when the truth is that the API has no such field. The Rainbow RSS feed
does provide one.

### Anything not modelled

`observation.raw` holds the untouched payload, so fields without a named
attribute — and any field Meteoclimatic adds in the future — remain reachable
without waiting for a library release.

### Time zones and the local civil day

Meteoclimatic stations are spread across several time zones, so never assume a
single offset. Each observation tells you the station's zone:

```python
observation.station.timezone   # 'Europe/Madrid', 'Atlantic/Canary', 'Europe/Lisbon'
observation.station.tzinfo     # ZoneInfo('Europe/Madrid')
observation.station.latitude   # 41.0
observation.station.longitude  # 1.0
observation.updated            # aware datetime, offset follows the station and DST
```

The daily values cover the station's **local civil day**, not a rolling 24-hour
window. They reset at local midnight in the station's own time zone and follow
daylight saving. `observation.local_day` is that date.

### Quality

```python
observation.quality.main           # 4  - a station category identifier, 0 if none
observation.quality.sensors["TMP"] # SensorFlags(status=True, quality=False)
```

`main`, `additional` and `transitional` are **integer identifiers of station
categories** (for example "Destacada"). They classify the station; they are not
per-reading validity, so do not use them to filter measurements.

The per-sensor `status` and `quality` flags are exposed but this library does not
act on them, and for now you should not either: their meaning is undefined by
Meteoclimatic, and real stations report `quality=False` on every sensor while
returning perfectly valid data. Availability is decided solely by a value being
present and not `None`.

## Errors

Everything derives from `MeteoclimaticError`, so a single `except` still catches
all of it.

| Exception | Raised when |
| --- | --- |
| `AuthenticationError` | The API key was rejected (`401`) |
| `StationNotFound` | Unknown, invalid or not-yet-migrated station (`404`) |
| `RateLimitError` | A usage limit was exceeded (`429`); carries `retry_after` |
| `BadRequestError` | Malformed request (`400`) |
| `TransportError` | Timeout, connection failure, or server error |
| `MalformedResponseError` | The response could not be understood |

```python
from meteoclimatic.alba import RateLimitError, StationNotFound
```

## Rate limits

Alba applies limits **per user**, across per-minute, per-hour and per-day windows,
so every station you poll with the same key shares one budget.

Sending a request while you are blocked **extends the block**, so the client
refuses to send once it knows one is active, raising `RateLimitError` immediately
without touching the network:

```python
client.blocked_until   # a datetime while blocked, otherwise None
```

The client never sleeps and never retries by itself. It reports how long is left
and lets you decide.

**Poll several stations with one client.** The client is tied to a credential, not
to a station, so reuse a single instance for every station sharing a key:

```python
client = Client(api_key)
for code in ("T415", "BU185", "TF90"):
    observation = client.get_current_data(code)
```

Creating one client per station means none of them knows about the others' blocks,
and they can extend each other's penalty.

## How often to poll

Stations publish roughly every five minutes; some every fifteen. Each response
carries a `ttl` you can schedule from:

```python
delay = observation.seconds_until_refresh(minimum=60)   # e.g. 226.0
```

This library never polls on its own. Scheduling is your application's decision.

## Asynchronous client

With the `async` extra installed:

```python
from meteoclimatic.alba import AsyncClient

async with AsyncClient(api_key) as client:
    observation = await client.get_current_data("T415")
```

If your application already keeps an `aiohttp` session, inject it and retain
ownership; the client will not close a session it did not create:

```python
client = AsyncClient(api_key, session=my_session)
```

## Legacy Rainbow (RSS) transport

> **Deprecated.** The RSS feed will be retired by Meteoclimatic, and the
> `meteoclimatic.rainbow` package is removed in version 1.0. Instantiating this
> client emits a `DeprecationWarning`.

```python
from meteoclimatic.rainbow import Client as RainbowClient

observation = RainbowClient().weather_at_station("ESCAT4300000043206B")
observation.weather.temp_current
observation.weather.condition       # Condition.sun - only Rainbow has this
```

The Rainbow transport keeps its own model (`Observation`, `Station`, `Weather`,
`Condition`), which describes the RSS feed. It is deliberately **not** shared with
Alba, because the two platforms report different information, and no conversion
between them is provided.

Existing code keeps working unchanged:

```python
from meteoclimatic import MeteoclimaticClient   # still the Rainbow client

observation = MeteoclimaticClient().weather_at_station("ESCAT4300000043206B")
```

## Migrating from Rainbow to Alba

1. Obtain an API Identifier from your Meteoclimatic profile.
2. Look up your station's Alba code on its page on the Meteoclimatic site. Keep
   your existing identifier as the storage key and treat the Alba code as an
   extra attribute.
3. Replace `weather_at_station()` with `get_current_data()`, and read values from
   the measurement groups instead of `observation.weather`.

What changes between the two platforms:

| | Rainbow (RSS) | Alba (API v3) |
| --- | --- | --- |
| Authentication | none | API key required |
| Station code | `ESCAT4300000043206B` | `T415` |
| Values on | `observation.weather` | grouped, e.g. `observation.temperature` |
| Field names | `temp_max`, `rain`, `wind_max` | `temperature.daily_max`, `precipitation.daily_total`, `wind.daily_gust` |
| Weather condition | provided | **not available** |
| Daily values | undocumented window | station's local civil day |
| Missing values | `-99` sentinel | `None` |
| Time zone | not provided | IANA name per station |
| Station URL | provided | not available |
| Rate limits | none documented | per user, with `Retry-After` |

## What changes in 1.0

Version 1.0 is released once Meteoclimatic retires the RSS feed. It will remove:

- the `meteoclimatic.rainbow` package and its `lxml` and `beautifulsoup4`
  dependencies;
- the `meteoclimatic.MeteoclimaticClient` alias;
- the top-level `Observation`, `Station`, `Weather` and `Condition` names, which
  currently refer to the Rainbow model; and
- the deprecated `meteoclimatic.client`, `meteoclimatic.feed`,
  `meteoclimatic.observation`, `meteoclimatic.station` and `meteoclimatic.weather`
  import paths.

`meteoclimatic.Client` and `meteoclimatic.alba` are unaffected: they mean the same
thing before and after 1.0.

## Contributing

Please feel free to submit issues or fork the repository and send pull requests to
update the library and fix bugs, implement support for new sentence types,
refactor code, etc.

## License

[MIT License](https://github.com/adrianmo/pymeteoclimatic/blob/master/LICENSE)
