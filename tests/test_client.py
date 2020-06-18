import os
import unittest
from urllib.error import HTTPError
from meteoclimatic.exceptions import StationNotFound, MeteoclimaticError
from meteoclimatic import MeteoclimaticClient
from unittest.mock import patch


class TestMeteoclimaticClient(unittest.TestCase):

    def setUp(self):
        self.client = MeteoclimaticClient()

    @patch('meteoclimatic.client.urlopen', autospec=True)
    def test_get_station_info_ok(self, mock_urlopen):
        f = open(os.path.join(os.path.dirname(
            __file__), "feeds", "full_station.xml"))
        mock_urlopen.return_value.read.return_value = f

        res = self.client.weather_at_station("ESCAT4300000043206B")

        mock_urlopen.assert_called_with(
            "https://www.meteoclimatic.net/feed/rss/ESCAT4300000043206B")
        self.assertEqual(res.station.code, "ESCAT4300000043206B")

    @patch('meteoclimatic.client.urlopen', autospec=True)
    def test_get_station_info_no_xml(self, mock_urlopen):
        mock_urlopen.return_value.read.return_value = ""

        with self.assertRaises(StationNotFound) as error:
            self.client.weather_at_station("ESCAT4300000043206B")
        self.assertEqual(error.exception.station_code, "ESCAT4300000043206B")
        self.assertEqual(str(
            error.exception), "Station code ESCAT4300000043206B did not return any item")

    @patch('meteoclimatic.client.urlopen', autospec=True)
    def test_get_station_info_404(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError("", 404, "Not Found", [], None)

        with self.assertRaises(MeteoclimaticError) as error:
            self.client.weather_at_station("ESCAT4300000043206B")
        self.assertEqual(str(
            error.exception), "Error fetching station data [status_code=404]")
