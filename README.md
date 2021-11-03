# Euroweather backend service
## TODO: Complete rewriting docs after forking!
## TODO: Add map of DWD-EU and application summary

&copy; 2021 NIBIO and Met Norway

Authors: Tor-Einar Skog (NIBIO) and Frank Thomas Tveter (Met Norway)

## License
```
 Copyright (c) 2021 NIBIO <https://www.nibio.no/> and Met Norway <https://www.met.no/>
 
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

The Euroweather service is a weather service that provides in-season data including approximately X hours of forecasts for all locations in Europe.
By using the hourly forecasts provided as open data from DWD (LINK) and storing them as "historical weather data", we have synthetic weather data
with 7 km resolution across the continent. 

The data are downloaded 8 times per day from DWD. The grib2 files are converted into NetCDF files containing 
only the parameters relevant for IPM Decisions. These are temperature, rainfall, relative humidity and wind speed.
For how to use the service, see the Euroweather frontend service (TODO LINK)

The backend service consists of to main parts: The downloading and extracting part and the interpolation service part

## Downloading and extracting data from Deutsche Wetterdienst (DWD)
The `perl/` folder contains the operative and data files. The `run_eu` script performs the actions needed. NetCDF files are named `outdir/all[yyyyMMddHH].nc`, with the time stamp reflecting the processing time on the DWD system. So, a set of files for one day will look like this:

```
-rw-rw-r-- 1 nibio nibio 795694784 Nov  2 05:31 all2021110200.nc
-rw-rw-r-- 1 nibio nibio 536232224 Nov  2 07:31 all2021110203.nc
-rw-rw-r-- 1 nibio nibio 795694784 Nov  2 11:31 all2021110206.nc
-rw-rw-r-- 1 nibio nibio 536232224 Nov  2 13:30 all2021110209.nc
-rw-rw-r-- 1 nibio nibio 657314752 Nov  2 17:31 all2021110212.nc
-rw-rw-r-- 1 nibio nibio 536232224 Nov  2 19:30 all2021110215.nc
-rw-rw-r-- 1 nibio nibio 778397280 Nov  2 23:31 all2021110218.nc
-rw-rw-r-- 1 nibio nibio 536232224 Nov  3 01:30 all2021110221.nc
```
**It is important that outdir/ is cleaned up before the start of every season (Jan 1st year X), since the interpolating service returns data from all the files in this folder.**

## Interpolating data by request of the frontend service
A python application for interpolating Using the Met Norway software [Fimex](https://github.com/metno/fimex) to read and interpolate the data. It's located in the `app/` folder. Run the app from that folder like this: `python3 gatekeeper.py`. The app then indexes all the NetCDF files in `../perl/outdir` and collects the requests from `*.res` files in the `../coms` folder. These files are simple text files with lat-lon pairs in them, with the site_id (frontend reference) as the file name. E.g. `1.req`, which may contain this text:

```
51.109 10.961
```
All of these coordinates are collected and the NetCDF files are analyzed and weather data are returned. The `*.req` files are returned by `*.res` files containing Json formatted weather data for that exact location, e.g. `1.req` is deleted and replaced by `1.res` containing the data for the location (51.109,10.961)

Heres an example of the returned result. `ref` denotes the processing time by DWD (when was the forecast model run), and `time` is the timestamp of the values. Since we have many NetCDF files for each day and these files contain x number of hourly time steps of forecasts, we have many values for the same time stamps. Many! So the front end application has to deal with this and select the optimal one for each hour. Currently this is done simply by choosing the value from the latest model run, meaning the one with the highest value of `ref`.

**TODO omit the first hourly step of all model runs/ref times, as that's an initial step of the model that may be a bit off (Move this TODO to frontend!!)**

```json
[
  {
    "ref": 1635066000,
    "time": 1635163200,
    "t2m": 283.0340576171875,
    "rh2m": 73.76285552978516,
    "rr": 0,
    "ff10m": 2.1369055294992325
  },
  {
    "ref": 1635066000,
    "time": 1635166800,
    "t2m": 283.6259460449219,
    "rh2m": 70.99372863769531,
    "rr": 0,
    "ff10m": 1.906816992313445
  },
  {
    "ref": 1635066000,
    "time": 1635170400,
    "t2m": 283.748291015625,
    "rh2m": 70.17800903320312,
    "rr": 0,
    "ff10m": 1.6672960126290226
  },
  {
    "ref": 1635066000,
    "time": 1635174000,
    "t2m": 283.1589050292969,
    "rh2m": 75.1905517578125,
    "rr": 0,
    "ff10m": 1.3367687115676812
  },
  {
    "ref": 1635076800,
    "time": 1635253200,
    "t2m": 284.7619934082031,
    "rh2m": 79.06034088134766,
    "ff10m": 2.4595363927522906
  },
  {
    "ref": 1635076800,
    "time": 1635256800,
    "t2m": 284.6748046875,
    "rh2m": 81.56535339355469,
    "rr": 0.0007519572973251343,
    "ff10m": 2.201740343804061
  }
]
```

## Configuring the system
### Software requirements
* Ubuntu Linux, tested with v 20
* Python3
* [Fimex](https://github.com/metno/fimex)
* Perl

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
1. The run_eu script (crontab **TODO ADD example**)


2. The gatekeeper process **TODO add rsync**

``` bash
python3 app/gatekeeper.py
```
