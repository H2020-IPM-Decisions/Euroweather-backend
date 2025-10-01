#!/usr/bin/python3
"""
    Copyright (C) 2023  Johannes Tobiassen Langvatn, Met Norway

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import os
import sys
import logging
import numpy as np
import xarray as xr
from datetime import timedelta, date
from config_and_logger import init_logging, init_config


logger = logging.getLogger(__name__)
init_logging(logger)
CONFIG = init_config()

ALL_PATH = CONFIG.get("all_path")
ARCHIVE_PATH = CONFIG.get("archive_path")
archive_cycles = CONFIG.get("archive_cycles")
main_cycles = CONFIG.get("main_cycles")
cycle_nr = len(archive_cycles)


def daterange(startdate, enddate):
    """Iterator to return single datetime for a range startdate to enddate"""
    for number in range(int((enddate - startdate).days)):
        yield startdate + timedelta(number)


def date_from_reftime(reftime):
    """
    Takes a zero-padded reftime string (YYYYMMDD) and returns a
    datetime date object
    """
    year = int(reftime[0:4])
    month = int(reftime[4:6])
    day = int(reftime[6:8])
    return date(year, month, day)


def accumulate_variables(input_netcdf_path, output_netcdf_path, forecast_drop=True):
    """
    Accumulates variables for use in EUROWEATHER (2)
    Assumes wind_speed instead of x_wind_10m and y_wind_10m
    """
    ds = xr.open_dataset(input_netcdf_path)

    ds["air_temperature_2m_max"] = ds["air_temperature_2m"].max(dim="time")
    ds["air_temperature_2m_min"] = ds["air_temperature_2m"].min(dim="time")
    ds["air_temperature_2m_mean"] = ds["air_temperature_2m"].mean(dim="time")

    ds["relative_humidity_2m_mean"] = ds["relative_humidity_2m"].mean(dim="time")
    ds["relative_humidity_2m_max"] = ds["relative_humidity_2m"].max(dim="time")

    ds["total_precipitation"] = ds["hourly_precipitation"].sum(dim="time")

    ds["mean_wind_speed_10m"] = ds["wind_speed_10m"].mean(dim="time")

    # Converts W/m2 to MJ/m2
    ds["daily_surface_net_downward_shortwave_flux"] = ds["surface_net_downward_shortwave_flux"].sum(dim="time") * 0.0036
    ds["daily_surface_net_downward_shortwave_flux"].attrs["units"] = "MJ/m^2"
    ds = ds.drop_vars(["air_temperature_2m", "relative_humidity_2m", "hourly_precipitation",
                       "wind_speed_10m", "surface_net_downward_shortwave_flux"])
    if forecast_drop is True:
        ds = ds.drop_vars(["forecast_reference_time"])
    ds.isel(time=[0]).to_netcdf(output_netcdf_path)
    ds.close()


def archive_day(reftime, day_before):
    """
    Archives a day of forecasted weather with date reftime (formatted as a string: YYYYMMDD),
    and the day_before (reftime of the day before)
    """
    yesterday = f"all{day_before}{main_cycles[-1]}.nc"
    ds_list = []
    not_first = False
    missing_cycles = 0
    # Going in the reversed order because we need to add 6 hours from the previous cycle if a cycle is missing
    for cycle in reversed(main_cycles):
        
        today_i = f"all{reftime}{cycle}.nc"
        logger.debug(today_i)
        logger.debug(not_first)
        logger.debug(missing_cycles)
        logger.debug(range(1, cycle_nr+1 + missing_cycles))
        if os.path.isfile(ALL_PATH+today_i):
            if not_first:
                ds_list.append(xr.open_dataset(ALL_PATH+today_i).isel(time=range(1, cycle_nr+1 + missing_cycles)).drop_vars("forecast_reference_time"))
            else:
                ds_list.append(xr.open_dataset(ALL_PATH+today_i).isel(time=range(1, cycle_nr+1 + missing_cycles)))
                not_first = True
            missing_cycles = 0
        else:
            logger.warning(f"File {ALL_PATH+today_i} does not exist, skipping this timestep when archiving {reftime}")
            missing_cycles = 6

    # Reverse the list to have it in chronological order
    ds_list.reverse()

    ds = xr.open_dataset(ALL_PATH+yesterday).isel(time=[cycle_nr-1, cycle_nr]).drop_vars("forecast_reference_time")

    out_ds = xr.merge([ds]+ds_list)
    out_ds["hourly_precipitation"] = out_ds["total_precipitation"].diff(dim="time")
    # Convert temperature from Kelvin to Celsius
    if out_ds["air_temperature_2m"].attrs["units"] == "K":
        out_ds["air_temperature_2m"].values = out_ds["air_temperature_2m"].values - 273.15
        out_ds["air_temperature_2m"].attrs["units"] = "degC"
    # Convert componental wind speed to wind speed
    out_ds["wind_speed_10m"] = np.sqrt(out_ds["x_wind_10m"]**2 + out_ds["y_wind_10m"]**2)

    temp = []
    for index, _ in enumerate(out_ds.time):
        # Reverts the non-accumulated (first hours) to original value
        # Must be -2 since index begins at 00, and we have want to restore 01
        # and time=0 maps to hour 23 (i.e time=1 -> hour 00 and time=2 hour 01)
        if (index-2)%cycle_nr == 0:
            temp_value = out_ds["total_precipitation"].isel(time=index).values
        else:
            temp_value = out_ds["hourly_precipitation"].isel(time=index).values
        temp_value = np.where(temp_value < 0, 0, temp_value)
        temp.append(temp_value)

    out_ds["hourly_precipitation"].values = temp
    out_ds = out_ds.drop_vars(["total_precipitation", "x_wind_10m", "y_wind_10m"])
    ds.close()
    return out_ds


if __name__ == "__main__":
    reftime_start = sys.argv[1]
    reftime_stop = sys.argv[2]

    start_date = date_from_reftime(reftime_start)
    day_before = (start_date - timedelta(days=1)).strftime("%Y%m%d")
    end_date = date_from_reftime(reftime_stop)

    for single_date in daterange(start_date, end_date):
        reftime = single_date.strftime("%Y%m%d")
        if os.path.isfile(f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc"):
            day_before = reftime
            continue
        ds = archive_day(reftime, day_before)
        ds.isel(time=range(1, 25)).to_netcdf(f"{ARCHIVE_PATH}daily_archive_{reftime}.nc")
        ds.close()

        accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{reftime}.nc", f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc")
        day_before = reftime
