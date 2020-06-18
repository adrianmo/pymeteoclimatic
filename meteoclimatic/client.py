from urllib.request import urlopen
from urllib.error import HTTPError
from bs4 import BeautifulSoup

from meteoclimatic.exceptions import MeteoclimaticError, StationNotFound
from meteoclimatic import Observation


class MeteoclimaticClient(object):
    """
    Entry point class providing clients for the Meteoclimatic service.
    """

    _base_url = "https://www.meteoclimatic.net/feed/rss/{station_code}"

    def weather_at_station(self, station_code):
        url = self._base_url.format(station_code=station_code)

        try:
            parse_xml_url = urlopen(url)
        except HTTPError as exc:
            raise MeteoclimaticError("Error fetching station data [status_code=%d]" %
                  (exc.getcode(), )) from exc

        xml_page = parse_xml_url.read()
        parse_xml_url.close()
        soup_page = BeautifulSoup(xml_page, "xml")
        items = soup_page.findAll("item")

        if len(items) == 0:
            raise StationNotFound(station_code)

        observation = Observation.from_feed_item(items[0])
        return observation
