class MeteoclimaticError(Exception):
    """Generic base class for Meteoclimatic exceptions"""
    pass


class StationNotFound(MeteoclimaticError):
    """Raised when the station code yields no Meteoclimatic station"""

    def __init__(self, station_code):
        self.station_code = station_code
        super().__init__("Station code %s did not return any item" % (station_code, ))
