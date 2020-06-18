import logging
from datetime import datetime
from meteoclimatic import Station, Weather, Condition
from meteoclimatic.feed import FeedItemHelper


class Observation:
    """
    A class representing the weather which is currently being observed from a
    certain station. The station is represented by the encapsulated *Station*
    object while the observed weather data are held by the encapsulated *Weather*
    object.

    :param reception_time: Timestamp telling when the weather obervation has
        been received from the station
    :type reception_time: `datetime.datetime`
    :param station: the *Station* relative to this observation
    :type station: *Station*
    :param weather: the *Weather* relative to this observation
    :type weather: *Weather*
    :returns: an *Observation* instance
    :raises: *ValueError* when negative values are provided as reception time
    """

    _feed_datetime_format = "%a, %d %b %Y %H:%M:%S %z"

    def __init__(self, reception_time: datetime, station: Station, weather: Weather):
        """Initialize the class."""
        if not isinstance(reception_time, datetime):
            raise ValueError(
                "reception_time is not an instance of datetime.datetime")
        self.reception_time = reception_time

        if not isinstance(station, Station):
            raise ValueError(
                "station is not an instance of meteoclimatic.Station")
        self.station = station

        if not isinstance(weather, Weather):
            raise ValueError(
                "weather is not an instance of meteoclimatic.Weather")
        self.weather = weather

    @classmethod
    def from_feed_item(cls, feed_item):
        """
        Parses an *Observation* instance out of an RSS feed item.
        :param feed_item: the input RSS feed item
        :type feed_item: `bs4.element.Tag`
        :returns: an *Observation* instance
        :raises: *ValueError* if it is not possible to parse the data
        """
        helper = FeedItemHelper(feed_item)

        station_name = feed_item.title.text
        station_code = helper.get_text("station_code")
        station_url = feed_item.link.text
        station = Station(station_name, station_code, station_url)

        reception_time = datetime.strptime(
            feed_item.pubDate.text, cls._feed_datetime_format)

        condition_str = helper.get_text("condition")
        try:
            condition = Condition(condition_str)
        except ValueError:
            logging.info(
                "Unrecognized condidition '%s', using literal value instead of meteoclimatic.Condition" % (condition_str, ))
            condition = condition_str
        temp_current = helper.get_float("temp_current")
        temp_max = helper.get_float("temp_max")
        temp_min = helper.get_float("temp_min")
        humidity_current = helper.get_float("humidity_current")
        humidity_max = helper.get_float("humidity_max")
        humidity_min = helper.get_float("humidity_min")
        pressure_current = helper.get_float("pressure_current")
        pressure_max = helper.get_float("pressure_max")
        pressure_min = helper.get_float("pressure_min")
        wind_current = helper.get_float("wind_current")
        wind_max = helper.get_float("wind_max")
        wind_bearing = helper.get_float("wind_bearing")
        rain = helper.get_float("rain")
        wind_max = helper.get_float("wind_max")

        weather = Weather(reception_time, condition,
                          temp_current, temp_max, temp_min,
                          humidity_current, humidity_max, humidity_min,
                          pressure_current, pressure_max, pressure_min,
                          wind_current, wind_max, wind_bearing,
                          rain)

        return cls(reception_time, station, weather)

    def __eq__(self, other):
        if not isinstance(other, Observation):
            return NotImplemented
        prop_names = list(self.__dict__)
        for prop in prop_names:
            if self.__dict__[prop] != other.__dict__[prop]:
                return False
        return True

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)
