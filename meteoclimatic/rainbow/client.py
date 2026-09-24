import warnings
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from bs4 import BeautifulSoup

from meteoclimatic.exceptions import MeteoclimaticError, StationNotFound
from meteoclimatic.rainbow.observation import Observation
from meteoclimatic.version import __version__


class Client(object):
    """Client for the legacy Meteoclimatic RSS feed (Rainbow platform).

    .. deprecated::
       Meteoclimatic is migrating to the Alba platform and the RSS feed will be
       retired. Use :class:`meteoclimatic.alba.Client` instead. This class, and
       the whole ``meteoclimatic.rainbow`` package, are removed in 1.0.
    """

    _base_url = "https://www.meteoclimatic.net/feed/rss/{station_code}"

    def __init__(self):
        """Initialize the class and warn that this transport is going away."""
        warnings.warn(
            "The Meteoclimatic RSS feed (Rainbow) is deprecated and will be "
            "retired; meteoclimatic.rainbow is removed in pymeteoclimatic 1.0. "
            "Use meteoclimatic.alba.Client (or meteoclimatic.Client) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def weather_at_station(self, station_code):
        url = self._base_url.format(station_code=station_code)

        req = Request(url, headers={"User-Agent": f"pymeteoclimatic/{__version__}"})

        try:
            parse_xml_url = urlopen(req)
        except HTTPError as exc:
            raise MeteoclimaticError(
                "Error fetching station data [status_code=%d]" % (exc.getcode(),)
            ) from exc

        xml_page = parse_xml_url.read()
        parse_xml_url.close()

        soup_page = BeautifulSoup(xml_page, "xml")
        items = soup_page.findAll("item")

        if len(items) == 0:
            raise StationNotFound(station_code)

        observation = Observation.from_feed_item(items[0])
        return observation
