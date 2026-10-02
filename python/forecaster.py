import os
import xarray as xr
import numpy as np

from contextlib import ExitStack
from datetime import timedelta
from day_archiver import (
    ALL_PATH,
    ARCHIVE_PATH,
    accumulate_variables,
    available_cycle_paths,
    archive_netcdf_encoding,
    date_from_reftime,
    main_cycles,
    write_netcdf_atomic,
)


FORECAST_DROP_VARIABLES = ["total_precipitation", "x_wind_10m", "y_wind_10m"]


def _without_forecast_metadata(dataset):
    dataset = dataset.drop_vars(["forecast_reference_time"], errors="ignore")
    if "hourly_precipitation" in dataset and dataset.sizes.get("time", 0) > 1:
        dataset = dataset.isel(time=slice(1, None))
    return dataset


def _select_date(dataset, target_date):
    date_string = target_date.strftime("%Y%m%d")
    selected = dataset.where(
        dataset.time.dt.strftime("%Y%m%d") == date_string,
        drop=True,
    )
    if selected.sizes.get("time", 0) != 24:
        raise ValueError(
            f"Expected 24 hourly values for {date_string}, "
            f"found {selected.sizes.get('time', 0)}"
        )
    return selected


def _write_daily_archive(dataset, target_date):
    output_path = os.path.join(
        ARCHIVE_PATH, f"daily_archive_{target_date.strftime('%Y%m%d')}.nc"
    )
    write_netcdf_atomic(
        dataset.drop_vars(FORECAST_DROP_VARIABLES, errors="ignore"),
        output_path,
    )
    return output_path


def _normalize_daily_time(dataset):
    if "time" not in dataset.coords or dataset.sizes.get("time", 0) != 1:
        raise ValueError("Daily accumulated datasets must contain exactly one time")

    time_value = dataset.time.values[0]
    for variable_name in dataset.data_vars:
        variable = dataset[variable_name]
        if variable_name != "projection_regular_ll" and "time" not in variable.dims:
            dataset[variable_name] = variable.expand_dims(time=[time_value])
    return dataset


def _write_year_with_forecast(year, daily_paths):
    historical_path = os.path.join(ARCHIVE_PATH, f"{year}.nc")
    output_path = os.path.join(ARCHIVE_PATH, f"{year}_with_forecast.nc")
    temporary_path = f"{output_path}.tmp"
    input_paths = []
    if os.path.isfile(historical_path):
        input_paths.append(historical_path)
    input_paths.extend(daily_paths)

    try:
        with ExitStack() as stack:
            datasets = [
                _normalize_daily_time(
                    stack.enter_context(xr.open_dataset(path))
                )
                for path in input_paths
            ]
            forecast_times = np.concatenate(
                [
                    dataset.time.values
                    for dataset in datasets[-len(daily_paths):]
                ]
            )
            combined = xr.concat(
                datasets,
                dim="time",
                data_vars="minimal",
                coords="minimal",
                compat="override",
                join="exact",
            ).sortby("time")

            _, reverse_indices = np.unique(
                combined.time.values[::-1], return_index=True
            )
            keep_indices = np.sort(
                combined.sizes["time"] - 1 - reverse_indices
            )
            combined = combined.isel(time=keep_indices)
            combined.to_netcdf(
                temporary_path,
                encoding=archive_netcdf_encoding(combined),
            )

        with xr.open_dataset(temporary_path) as written:
            written_forecast = written.sel(time=forecast_times)
            if written_forecast.sizes.get("time", 0) != len(forecast_times):
                raise ValueError("Yearly archive is missing forecast dates")
            for variable_name in written_forecast.data_vars:
                if variable_name == "projection_regular_ll":
                    continue
                if int(written_forecast[variable_name].count()) == 0:
                    raise ValueError(
                        f"Yearly archive contains no values for {variable_name}"
                    )

        os.replace(temporary_path, output_path)
    finally:
        if os.path.isfile(temporary_path):
            os.unlink(temporary_path)


def forecast_archiver(inpath, reftime):
    """
    Archive daily aggregates for today and the next two days.

    Today's hours are selected from all available model cycles, preferring the
    newest cycle for duplicate valid times. Future days come from the current
    model run.
    """
    date_today = date_from_reftime(reftime)
    cycle = reftime[-2:]
    if cycle not in main_cycles:
        raise ValueError(f"Unsupported model cycle {cycle}")

    previous_date = (date_today - timedelta(days=1)).strftime("%Y%m%d")
    cycle_paths = available_cycle_paths(previous_date)
    cycle_paths.extend(
        available_cycle_paths(
            reftime[:-2],
            main_cycles[:main_cycles.index(cycle) + 1],
        )
    )
    if inpath not in cycle_paths:
        cycle_paths.append(inpath)

    target_dates = [date_today + timedelta(days=offset) for offset in range(3)]
    daily_archive_paths = []
    with ExitStack() as stack:
        cycle_datasets = [
            _without_forecast_metadata(
                stack.enter_context(xr.open_dataset(path))
            )
            for path in cycle_paths
            if os.path.isfile(path)
        ]
        if not cycle_datasets:
            raise FileNotFoundError("No forecast datasets are available to archive")

        combined = xr.concat(
            cycle_datasets,
            dim="time",
            data_vars="minimal",
            coords="minimal",
            compat="override",
            join="exact",
        )
        _, reverse_indices = np.unique(
            combined.time.values[::-1], return_index=True
        )
        keep_indices = np.sort(combined.sizes["time"] - 1 - reverse_indices)
        combined = combined.isel(time=keep_indices).sortby("time")

        for target_date in target_dates:
            daily_archive_paths.append(
                _write_daily_archive(
                    _select_date(combined, target_date), target_date
                )
            )

    daily_accumulated_paths = []
    for target_date, daily_archive_path in zip(
        target_dates, daily_archive_paths
    ):
        accumulated_path = os.path.join(
            ARCHIVE_PATH,
            f"daily_accumulated_{target_date.strftime('%Y%m%d')}.nc",
        )
        accumulate_variables(
            daily_archive_path, accumulated_path, forecast_drop=False
        )
        daily_accumulated_paths.append(accumulated_path)

    _write_year_with_forecast(date_today.strftime("%Y"), daily_accumulated_paths)


def forecaster(inpath, outpath):
    """
    Converts to wind speed, calculates hourly precipitation,
    converts temperature to Celsius if temperature is in Kelvin
    converts ASOB_S [W/m2] (Average Net short-wave radiation flux at surface)
    to Hourly Net short-wave radiation [W/m2] (Which will be computed to daily values)
    """
    required_variables = {
        "ASOB_S",
        "air_temperature_2m",
        "forecast_reference_time",
        "relative_humidity_2m",
        "time",
        "total_precipitation",
        "x_wind_10m",
        "y_wind_10m",
    }
    temporary_path = f"{outpath}.tmp"

    try:
        with xr.open_dataset(inpath) as ds:
            missing_variables = required_variables.difference(ds.variables)
            if missing_variables:
                raise ValueError(
                    "Cannot process forecast; missing variables: "
                    + ", ".join(sorted(missing_variables))
                )
            if ds.sizes.get("time", 0) < 2:
                raise ValueError("Cannot process a forecast with fewer than two times")
            if not np.all(np.diff(ds.time.values) > np.timedelta64(0, "s")):
                raise ValueError("Forecast times must be strictly increasing")

            lead_hours = (
                ds.time - ds.forecast_reference_time
            ) / np.timedelta64(1, "h")
            step_hours = lead_hours.diff(dim="time")
            if bool((step_hours <= 0).any().item()):
                raise ValueError("Forecast lead times must be strictly increasing")

            surface_rad = "surface_net_downward_shortwave_flux"
            accumulated_radiation = ds["ASOB_S"] * lead_hours
            ds[surface_rad] = (
                accumulated_radiation.diff(dim="time") / step_hours
            )
            ds[surface_rad].attrs = {
                "standard_name": surface_rad,
                "long_name": "hourly mean surface net downward shortwave flux",
                "units": "W/m^2",
            }

            ds["hourly_precipitation"] = (
                ds["total_precipitation"].diff(dim="time").clip(min=0)
            )
            ds["hourly_precipitation"].attrs = {
                "long_name": "hourly precipitation",
                "standard_name": "precipitation_amount",
                "units": "kg m^-2",
            }

            if ds["air_temperature_2m"].attrs.get("units") == "K":
                temperature_attrs = ds["air_temperature_2m"].attrs.copy()
                ds["air_temperature_2m"] = ds["air_temperature_2m"] - 273.15
                temperature_attrs["units"] = "degC"
                ds["air_temperature_2m"].attrs = temperature_attrs

            ds["relative_humidity_2m"].attrs["units"] = "%"

            ds["wind_speed_10m"] = np.hypot(
                ds["x_wind_10m"], ds["y_wind_10m"]
            )
            ds["wind_speed_10m"].attrs = {
                "standard_name": "wind_speed",
                "long_name": "wind speed at 10 m",
                "units": "m s^-1",
            }

            ds = ds.drop_vars(["ASOB_S"])
            ds.to_netcdf(temporary_path)

        os.replace(temporary_path, outpath)
    finally:
        if os.path.isfile(temporary_path):
            os.unlink(temporary_path)


if __name__ == "__main__":
    forecaster("outdir/all2024031500_tmp.nc", "outdir/all2024031500.nc")
