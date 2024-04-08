import os
import xarray as xr
import numpy as np

from datetime import timedelta
from day_archiver import accumulate_variables, date_from_reftime, main_cycles, cycle_nr, ALL_PATH, ARCHIVE_PATH


def forecast_archiver(inpath, reftime):
    """
    Collects the latest available forecasts for the hours constituting today, tomorrow and day
    after tomorrow (date_today, date_plus_1, date_plus_2).
    Creates a temporary daily_archive, daily_accumulated from these forecasts, and appends the
    accumulated files to the year file.
    """
    date_today = date_from_reftime(reftime)
    yesterday = f"all{(date_today - timedelta(days=1)).strftime('%Y%m%d')}{main_cycles[-1]}.nc"

    date_plus_1 = date_today + timedelta(days=1)
    date_plus_2 = date_today + timedelta(days=2)
    cycle = reftime[-2:]
    # need 24 from yesterday, list of time to prevent the time-dimension from collapsing
    ds_yesterday = xr.open_dataset(ALL_PATH+yesterday).isel(time=[cycle_nr]).drop_vars("forecast_reference_time")
    all_0 = f"all{reftime[:-2]}{main_cycles[0]}.nc"
    all_1 = f"all{reftime[:-2]}{main_cycles[1]}.nc"
    all_2 = f"all{reftime[:-2]}{main_cycles[2]}.nc"
    all_ds = xr.open_dataset(inpath).drop_vars("forecast_reference_time")

    if cycle == "00":
        offset = 25
        first_day = range(1, offset)
        ds_list = [ds_yesterday, all_ds.isel(time=first_day)]
    elif cycle == "06":
        offset = 25-7
        first_day = range(1, offset)
        all_00 = xr.open_dataset(ALL_PATH+all_0).isel(time=range(1, cycle_nr+1)).drop_vars("forecast_reference_time")
        ds_list = [ds_yesterday, all_00, all_ds.isel(time=first_day)]
    elif cycle == "12":
        offset = 25-13
        first_day = range(1, offset)
        all_00 = xr.open_dataset(ALL_PATH+all_0).isel(time=range(1, cycle_nr+1)).drop_vars("forecast_reference_time")
        all_06 = xr.open_dataset(ALL_PATH+all_1).isel(time=range(1, cycle_nr+1)).drop_vars("forecast_reference_time")
        ds_list = [ds_yesterday, all_00, all_06, all_ds.isel(time=first_day)]
    elif cycle == "18":
        offset = 25-19
        first_day = range(1, offset)
        all_00 = xr.open_dataset(ALL_PATH+all_0).isel(time=range(1, cycle_nr+1)).drop_vars("forecast_reference_time")
        all_06 = xr.open_dataset(ALL_PATH+all_1).isel(time=range(1, cycle_nr+1)).drop_vars("forecast_reference_time")
        all_12 = xr.open_dataset(ALL_PATH+all_2).isel(time=range(1, cycle_nr+1)).drop_vars("forecast_reference_time")
        ds_list = [ds_yesterday, all_00, all_06, all_12, all_ds.isel(time=first_day)]
    second_day = range(offset, offset + 24)
    third_day = range(offset + 24, offset + 24*2)

    out_ds = xr.merge(ds_list)
    out_ds = out_ds.drop_vars(["total_precipitation", "x_wind_10m", "y_wind_10m"])
    out_ds.to_netcdf(f"{ARCHIVE_PATH}daily_archive_{reftime[:-2]}.nc")

    out_second = all_ds.isel(time=second_day)
    out_second = out_second.drop_vars(["total_precipitation", "x_wind_10m", "y_wind_10m"])
    out_second.to_netcdf(f"{ARCHIVE_PATH}daily_archive_{date_plus_1.strftime('%Y%m%d')}.nc")

    out_third = all_ds.isel(time=third_day)
    out_third = out_third.drop_vars(["total_precipitation", "x_wind_10m", "y_wind_10m"])
    out_third.to_netcdf(f"{ARCHIVE_PATH}daily_archive_{date_plus_2.strftime('%Y%m%d')}.nc")

    # Is this needed?, we need to acess the files created above.
    out_ds.close()
    out_second.close()
    out_third.close()
    accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{reftime[:-2]}.nc",
                         f"{ARCHIVE_PATH}daily_accumulated_{reftime[:-2]}.nc", forecast_drop=False)
    accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{date_plus_1.strftime('%Y%m%d')}.nc",
                         f"{ARCHIVE_PATH}daily_accumulated_{date_plus_1.strftime('%Y%m%d')}.nc", forecast_drop=False)
    accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{date_plus_2.strftime('%Y%m%d')}.nc",
                         f"{ARCHIVE_PATH}daily_accumulated_{date_plus_2.strftime('%Y%m%d')}.nc", forecast_drop=False)
    year = date_today.strftime("%Y")
    if os.path.isfile(f"{ARCHIVE_PATH}{year}.nc"):
        ds = xr.open_mfdataset([f"{ARCHIVE_PATH}{year}.nc",
                               f"{ARCHIVE_PATH}daily_accumulated_{reftime[:-2]}.nc",
                               f"{ARCHIVE_PATH}daily_accumulated_{date_plus_1.strftime('%Y%m%d')}.nc",
                               f"{ARCHIVE_PATH}daily_accumulated_{date_plus_2.strftime('%Y%m%d')}.nc"],
                               lock=False)
    else:
        ds = xr.open_mfdataset([
                               f"{ARCHIVE_PATH}daily_accumulated_{reftime[:-2]}.nc",
                               f"{ARCHIVE_PATH}daily_accumulated_{date_plus_1.strftime('%Y%m%d')}.nc",
                               f"{ARCHIVE_PATH}daily_accumulated_{date_plus_2.strftime('%Y%m%d')}.nc"],
                               lock=False)
    ds.to_netcdf(f"{ARCHIVE_PATH}{year}_with_forecast_tmp.nc")
    ds.close()
    os.rename(f"{ARCHIVE_PATH}{year}_with_forecast_tmp.nc", f"{ARCHIVE_PATH}{year}_with_forecast.nc")


def forecaster(inpath, outpath):
    """
    Converts to wind speed, calculates hourly precipitation,
    converts temperature to Celsius if temperature is in Kelvin
    """
    ds = xr.open_dataset(inpath)
    ds["hourly_precipitation"] = ds["total_precipitation"].diff(dim="time")
    if ds["air_temperature_2m"].attrs["units"] == "K":
        ds["air_temperature_2m"].values = ds["air_temperature_2m"].values - 273.15
        ds["air_temperature_2m"].attrs["units"] = "degC"
    ds["wind_speed_10m"] = np.sqrt(ds["x_wind_10m"]**2 + ds["y_wind_10m"]**2)
    ds.to_netcdf(outpath)
    ds.close()


if __name__ == "__main__":
    forecaster("outdir/all2024031500_tmp.nc", "outdir/all2024031500.nc")