import re


class FeedItemHelper(object):
    """Helper class to get content from a Meteoclimatic RSS feed item."""

    _regex_pattern = r"\[\[\<(?P<station_code>\w+);\((?P<temp_current>-?[0-9,]+);(?P<temp_max>-?[0-9,]+);(?P<temp_min>-?[0-9,]+);(?P<condition>\w*)\);\((?P<humidity_current>-?[0-9,]*);(?P<humidity_max>-?[0-9,]*);(?P<humidity_min>-?[0-9,]*)\);\((?P<pressure_current>-?[0-9,]*);(?P<pressure_max>-?[0-9,]*);(?P<pressure_min>-?[0-9,]*)\);\((?P<wind_current>-?[0-9,]*);(?P<wind_max>-?[0-9,]*);(?P<wind_bearing>-?[0-9,]*)\);\((?P<rain>-?[0-9,]*)\);"  # noqa: E501

    def __init__(self, feed_item):
        """Initialize the class."""
        self.match = re.search(self._regex_pattern, str(feed_item.description))
        if not self.match:
            raise ValueError("Could not parse station information")

    def get_text(self, field_name):
        """Return the value in 'field_name' from the item or None if not found."""
        try:
            value = self.match.group(field_name)
        except IndexError:
            return None
        if len(value) == 0:
            return None
        return value

    def get_float(self, field_name):
        """Return the value in 'field_name' from the item or None if not found."""
        value = self.get_text(field_name)
        if value is None:
            return None
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            return None
        if value == -99.0:
            # Meteoclimatic returns -99,0 when the station does not provide the value
            return None
        return value
