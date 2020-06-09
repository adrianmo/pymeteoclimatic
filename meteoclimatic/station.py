class Station:
    """
    A class representing a Meteoclimatic station.

    :param name: Name of the station
    :type name: `str`
    :param code: Meteoclimatic code of the station
    :type code: `str`
    :param url: URL of the station
    :type url: `str`
    :returns: a *Station* instance
    :raises: *ValueError* when invalid empty or null values are provided
    """

    def __init__(self, name: str, code: str, url: str):
        """Initialize the class."""
        if name is None or len(name) == 0:
            raise ValueError("Station name cannot be empty")
        self.name = name

        if code is None or len(code) == 0:
            raise ValueError("Station code cannot be empty")
        self.code = code
        self.url = url

    def __eq__(self, other):
        if not isinstance(other, Station):
            return NotImplemented
        prop_names = list(self.__dict__)
        for prop in prop_names:
            if self.__dict__[prop] != other.__dict__[prop]:
                return False
        return True

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)
