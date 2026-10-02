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
from contextlib import ExitStack
from datetime import timedelta, date
from config_and_logger import init_logging, init_config


logger = logging.getLogger(__name__)
init_logging(logger)
CONFIG = init_config()

ALL_PATH = CONFIG.get("all_path")
ARCHIVE_PATH = CONFIG.get("archive_path")
main_cycles = CONFIG.get("main_cycles")
GRID_MAPPING_VARIABLE = "projection_regular_ll"


def archive_netcdf_encoding(dataset):
    if "time" not in dataset.variables:
        return {}
    return {
        "time": {
            "dtype": "float64",
            "units": "seconds since 1970-01-01 00:00:00",
            "calendar": "proleptic_gregorian",
            "_FillValue": None,
        }
    }


def write_netcdf_atomic(dataset, output_path):
    temporary_path = f"{output_path}.tmp"
    try:
        dataset.to_netcdf(
            temporary_path,
            encoding=archive_netcdf_encoding(dataset),
        )
        os.replace(temporary_path, output_path)
    finally:
        if os.path.isfile(temporary_path):
            os.unlink(temporary_path)


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


def available_cycle_paths(reftime, cycles=None):
    if cycles is None:
        cycles = main_cycles
    return [
        os.path.join(ALL_PATH, f"all{reftime}{cycle}.nc")
        for cycle in cycles
        if os.path.isfile(
            os.path.join(ALL_PATH, f"all{reftime}{cycle}.nc")
        )
    ]


def normalize_grid_mapping(dataset):
    if GRID_MAPPING_VARIABLE not in dataset:
        return dataset
    attributes = dataset[GRID_MAPPING_VARIABLE].attrs
    dataset = dataset.drop_vars(GRID_MAPPING_VARIABLE)
    dataset[GRID_MAPPING_VARIABLE] = xr.DataArray(
        np.int32(0),
        attrs=attributes,
    )
    return dataset


def accumulate_variables(input_netcdf_path, output_netcdf_path, forecast_drop=True):
    """
    Accumulates variables for use in EUROWEATHER (2)
    Assumes wind_speed instead of x_wind_10m and y_wind_10m
    """
    with xr.open_dataset(input_netcdf_path) as ds:
        daily_time = ds.time.values[0]
        ds["air_temperature_2m_max"] = ds["air_temperature_2m"].max(dim="time")
        ds["air_temperature_2m_min"] = ds["air_temperature_2m"].min(dim="time")
        ds["air_temperature_2m_mean"] = ds["air_temperature_2m"].mean(dim="time")

        ds["relative_humidity_2m_mean"] = ds["relative_humidity_2m"].mean(
            dim="time"
        )
        ds["relative_humidity_2m_max"] = ds["relative_humidity_2m"].max(dim="time")

        ds["total_precipitation"] = ds["hourly_precipitation"].sum(dim="time")
        ds["mean_wind_speed_10m"] = ds["wind_speed_10m"].mean(dim="time")

        ds["daily_surface_net_downward_shortwave_flux"] = (
            ds["surface_net_downward_shortwave_flux"].sum(dim="time") * 0.0036
        )
        ds["daily_surface_net_downward_shortwave_flux"].attrs["units"] = "MJ/m^2"
        ds = ds.drop_vars(
            [
                "air_temperature_2m",
                "relative_humidity_2m",
                "hourly_precipitation",
                "wind_speed_10m",
                "surface_net_downward_shortwave_flux",
            ]
        )
        if forecast_drop:
            ds = ds.drop_vars(["forecast_reference_time"], errors="ignore")
        ds = ds.drop_dims("time").expand_dims(time=[daily_time])
        ds = normalize_grid_mapping(ds)
        write_netcdf_atomic(ds, output_netcdf_path)


def archive_day(reftime, day_before, output_path=None):
    """
    Archives a day of forecasted weather with date reftime (formatted as a string: YYYYMMDD),
    and the day_before (reftime of the day before). When output_path is given,
    streams the result to that file instead of loading it into memory.
    """
    available_paths = available_cycle_paths(day_before)
    available_paths.extend(available_cycle_paths(reftime))
    if not available_paths:
        raise FileNotFoundError(f"No forecast files are available for {reftime}")

    with ExitStack() as stack:
        target_date = np.datetime64(date_from_reftime(reftime))
        hourly_datasets = {}
        for path in available_paths:
            dataset = stack.enter_context(xr.open_dataset(path))
            if "hourly_precipitation" not in dataset:
                raise ValueError(
                    f"{path} has not been processed by forecaster"
                )
            dataset = dataset.drop_vars(
                ["forecast_reference_time"], errors="ignore"
            )
            dataset = dataset.isel(time=slice(1, None))
            for index, time_value in enumerate(dataset.time.values):
                if np.datetime64(time_value, "D") == target_date:
                    hourly_datasets[np.datetime64(time_value, "ns")] = (
                        dataset.isel(time=[index])
                    )

        if len(hourly_datasets) != 24:
            raise ValueError(
                f"Expected 24 hourly values for {reftime}, "
                f"found {len(hourly_datasets)}"
            )

        selected = xr.concat(
            [hourly_datasets[time] for time in sorted(hourly_datasets)],
            dim="time",
            data_vars="minimal",
            coords="minimal",
            compat="override",
            join="exact",
        )
        archived = selected.drop_vars(
            ["total_precipitation", "x_wind_10m", "y_wind_10m"],
            errors="ignore",
        )
        archived = normalize_grid_mapping(archived)
        if output_path is not None:
            write_netcdf_atomic(archived, output_path)
            return None
        return archived.load()


def append_daily_to_year(daily_path, year_path):
    temporary_path = f"{year_path}.tmp"
    appended = True
    try:
        with ExitStack() as stack:
            daily = normalize_grid_mapping(
                stack.enter_context(xr.open_dataset(daily_path))
            )
            datasets = []
            if os.path.isfile(year_path):
                historical = normalize_grid_mapping(
                    stack.enter_context(xr.open_dataset(year_path))
                )
                if np.isin(daily.time.values, historical.time.values).any():
                    appended = False
                datasets.append(historical)
            if appended:
                datasets.append(daily)

            if len(datasets) == 1:
                combined = datasets[0]
            else:
                combined = xr.concat(
                    datasets,
                    dim="time",
                    data_vars="minimal",
                    coords="minimal",
                    compat="override",
                    join="exact",
                ).sortby("time")
            combined.to_netcdf(
                temporary_path,
                encoding=archive_netcdf_encoding(combined),
            )

        os.replace(temporary_path, year_path)
        return appended
    finally:
        if os.path.isfile(temporary_path):
            os.unlink(temporary_path)


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
        archive_day(
            reftime,
            day_before,
            output_path=f"{ARCHIVE_PATH}daily_archive_{reftime}.nc",
        )

        accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{reftime}.nc", f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc")
        day_before = reftime
