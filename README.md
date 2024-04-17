# Euroweather

This application downloads gridded weather forecasts covering Europe from [Deutscher Wetterdienst](https://www.dwd.de/) and stores then as sets of NetCDF files. The data spans from the start of the season (or later) and approximately 72 hours ahead of time. 

The files are suitable for calculating pest/disease risk maps for Europe.


![Example temperature map showing the covered area](./map.png "Example temperature map showing the covered area")

&copy; 2024 [Met Norway](https://www.met.no/en) and [NIBIO](https://nibio.no/en) 

Authors: Johannes Tobiassen Langvatn (Met Norway) and Tor-Einar Skog (NIBIO)

## License
```
 Copyright (c) 2024 NIBIO <https://www.nibio.no/> and Met Norway <https://www.met.no/>
 
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Affero General Public License for more details.
 
 You should have received a copy of the GNU Affero General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
 
```

By using the hourly forecasts provided as [open data from Deutscher Wetterdienst (DWD)](https://www.dwd.de/EN/ourservices/opendata/opendata.html) and storing them as "historical weather data", we have synthetic weather data with 7 km resolution across the continent. 

The data are downloaded 4 times per day from [DWD](http://opendata.dwd.de/weather/nwp/icon-eu/grib/). The grib2 files are converted into NetCDF files containing 
only the parameters relevant for IPM Decisions. These are 

* Temperature (at 2m in &deg;C)
* Total precipitation (in mm)
* Relative humidity (at 2m in %)
* Wind speed (at 10m in m/s)

## Data flow
The data flow is illustrated below
![Data flow](./docs/illustrations/euroweather2_data_flow.png "Data flow")


### Downloading and extracting data from Deutscher Wetterdienst (DWD)
Every six hours (00, 06, 12, 18), DWD issues their main forecast files, which are single files for each parameter and every hour (0-78). So for each run we download five files (RELHUM, TOT_PREC, T_2M, U_10M, v_10M) times 79 hours = 445 files. These 445 files are concatenated into one grib2 file for the DWD "six-hour run", e.g. `python/outdir/forecast_2024041618.grib2`

### Converting from grib2 to NetCDF and adapting parameters
The parameters in the `forecast_*` files need a bit of conversion: Temperature from K to &deg;C and the wind vectors need to be converted into speed. The file format is also converted to NetCDF, e.g. `python/outdir/all2024041618.nc`

### Organizing data into daily files
Each `all_*` file contains 79 hours of values, so there's a lot of overlap. The values for the most recent runs are kept, and hourly values are collected in groups of DD00-DD23 (UTC), e.g. `python/outdir/daily_archive_20240416.nc`. Files up until the day after tomorrow are generated.

### Aggregating daily values
Daily values are aggregated from the hourly sets, so that the daily parameters are:
* Temperature (at 2m in &deg;C): mean, minimum and maximum
* Total precipitation (in mmm)
* Relative humidity (at 2m in %): mean and maximum
* Wind speed (at 10m in m/s): mean
These aggregate values are placed in these files:
* `python/outdir/daily_accumulated_20240417.nc` (one per day)
* `python/outdir/2024.nc` (all daily values in one year)
* `python/outdir/2024_with_forecasts.nc` (all daily values in one year, including today, tomorrow and the day after)



## Configuring the system
### Software requirements
* Ubuntu Linux, tested with v 22
* Python3 including xarray/numpy and netcdf4
* [Fimex](https://github.com/metno/fimex)

### Hardware requirements
* SSD (preferably) disk with at least 2TB of storage space (for one season worth of NetCDF weather data files)


#### Installing Fimex and Python requirements
Example using Ubuntu

``` bash
add-apt-repository ppa:met-norway/fimex
apt-get update
apt-get install --assume-yes fimex-1.6-bin fimex-1.6-share libfimex-1.6-0 python3-pyfimex0-1.6
```

From the root folder of the source code:

``` bash
sudo pip3 install -r requirements.xt
```

### Running the app
There are two processes that need to be run regularly
#### 1. The run_eu script
Should be run at least 4 times per day

An example of a crontab entry:
```bash
# m h  dom mon dow   command
30 * * * * cd /opt/Euroweather-backend/perl; ./run_eu > ./download.log
```

#### 2. daily_archiver.py
Should be run at least once per day, after the last daily data has been produced by DWD, so shortly after midnight.

An example of a crontab entry:
```bash
# m h  dom mon dow   command
0 1 * * * /opt/Euroweather-backend/python/daily_archiver.py
```

### Data maintenance
`daily_archiver.py` automatically generates new files - such as YYYY.nc, but it deletes nothing. The application mananger must archive data as they see fit. A yearly maintenance recommendation could be:
* Keep the source files from DWD

    There are so many of them that the regular `mv` or `cp` commands don't work. This works, however: `find . -name 'icon-eu_europe_regular-lat-lon_single-level_2023*' -exec mv {} /opt/archive/2023/grib/ \;` (Substitute with your paths and year)
* Delete last year's `forecast_*.grib2` files
* Delete last year's `all*.nc` files
* Delete last year's `daily_accumulated_*` files
* Keep `daily_archive_*.nc` and `YYYY.nc`
