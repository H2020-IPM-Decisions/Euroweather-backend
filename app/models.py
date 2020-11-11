
class WeatherData:
    def __init__(self, *args, **kwargs):
        self.timeStart = kwargs.get("timeStart", None)
        self.timeEnd = kwargs.get("timeEnd", None)
        self.interval = kwargs.get("interval", None)
        self.QC = kwargs.get("QC", None)
        self.weatherParameters = kwargs.get("weatherParameters", None)
        self.locationWeatherData = []


    def as_dict(self):
        retval = vars(self)
        lwds_dict = []
        for lwd in self.locationWeatherData:
            lwds_dict.append(lwd.as_dict())
        retval["locationWeatherData"] = lwds_dict
        # Add location weather data
        return retval 

class LocationWeatherData:
    def __init__(self, *args, **kwargs):
        self.altitude = kwargs.get("altitude", None)
        self.longitude = kwargs.get("longitude", None)
        self.latitude = kwargs.get("latitude", None)
        self.data = []


    def as_dict(self):
        retval = vars(self)
        # Add location weather data
        return retval 