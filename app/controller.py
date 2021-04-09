from models import WeatherData, LocationWeatherData
from interpolator import Interpolator
from negotiator import Negotiator
from datetime import datetime
import time
import os
import sys

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

filename= SITE_ROOT + '/../weather_data/all.nc'
#config= SITE_ROOT + '/cdmGribReaderConfig.xml'
#print (filename, file =sys.stderr)
param_mapping = {
    1001: "t2m",
    1002: "t2m",
    2001: "rr",
    3001: "rh2m",
    3002: "rh2m",
    4002: "ff10m",
    4012: "ff10m"
}

kelvin_0c = 272.15

interval = 3600 # Hourly values, always

class Controller:
    def __init__(self):
        pass
        #start_time = time.time()
        #self.ip = Interpolator(filename, config)
        #print("New Controller initialized. It took %s seconds." % (time.time() - start_time), file =sys.stderr)

    def get_weather_data(self, longitude, latitude, parameters):
        # If no parameters, use all that DWD provides
        if parameters == None:
            parameters = [1001,2001,3001,4012]
        qc = [1 for p in parameters] # We trust Deutsche WetterDienst. Aber natürlich!
        
        retval = WeatherData(
            weatherParameters=parameters, interval=3600
            )
        location_weather_data = LocationWeatherData(longitude=longitude, latitude=latitude, QC=qc)
        

        # TESTING
        
        #ip=Interpolator(filename,config);

        lons = [float(longitude)] # Working example: [10.965]
        lats = [float(latitude)] # Working example: [50.109]
        #res = self.ip.interpolate(lats,lons)[0] # Using only one coordinate for now

        directory= SITE_ROOT + "/../coms";
        negotiator=Negotiator(directory);
        path=negotiator.request(lats,lons);
        res=negotiator.listen(path);
        #print(ret);

        #return retval.as_dict()

        
        #print("Results:",res)

        first_epoch = res[0]["time"]
        last_epoch = res[len(res)-1]["time"]

        retval.timeStart = "%sZ" % datetime.utcfromtimestamp(first_epoch).isoformat()
        retval.timeEnd = "%sZ" % datetime.utcfromtimestamp(last_epoch).isoformat()

        data = [None] * (1 + int((last_epoch - first_epoch) / interval))
        for time_paramdict in res:
            row_index = int((time_paramdict["time"] - first_epoch) / interval)
            data[row_index] = [None] * len(parameters)
            for idx, parameter in enumerate(parameters):
                strval = time_paramdict.get(param_mapping[parameter], None)
                value = float(strval) if strval is not None else None
                if value is not None and parameter < 2000: # Temp is in kelvin
                    value = value - kelvin_0c
                # Rainfall must be shifted 1 hr back
                if parameter == 2001 and row_index > 0:
                    data[row_index - 1][idx] = value
                else:
                    data[row_index][idx] = value
            #print("%sZ: %s" % (datetime.utcfromtimestamp(time_paramdict["time"]).isoformat(), time_paramdict["rr"]))
        
        location_weather_data.data = data
        retval.locationWeatherData.append(location_weather_data)
        return retval.as_dict()