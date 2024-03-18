import xarray as xr
import numpy as np


def forecast_accumulator(inpath, outpath):
    """
    Accumulates forecasted variables,
    need a design decision. Accumulates all three days ahead?
    Accumulates into 3 files or 1 file, update only the 2 files most into the future?
    """
    pass


def append_accumulated(inpath, reftime, year=None):
    pass


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