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
import xarray as xr
from datetime import timedelta, date
from config_and_logger import init_logging, init_config
from day_archiver import accumulate_variables, archive_day

logger = logging.getLogger(__name__)
init_logging(logger)
CONFIG = init_config()

YEAR = date.today().year
reftime = date.today() - timedelta(days=1)
day_before = date.today() - timedelta(days=2)
reftime = reftime.strftime("%Y%m%d")
day_before = day_before.strftime("%Y%m%d")

archive_cycles = CONFIG.get("archive_cycles")
main_cycles = CONFIG.get("main_cycles")
ARCHIVE_PATH = CONFIG.get("archive_path")

ds = archive_day(reftime, day_before)
logger.debug("Creating the NetCDF file")
ds.isel(time=range(1, 25)).load().to_netcdf(f"{ARCHIVE_PATH}daily_archive_{reftime}.nc")
ds.close()
logger.debug("Done creating the NetCDF file")
logger.debug("Accumulating variables")
accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{reftime}.nc", f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc")
logger.debug("Done accumulating variables")
logger.debug("Appending to year file")
# Append newly created accumulated to the year file if it exists:
# If it does not exist, rename daily_accumulated_REFTIME.nc to YEAR.nc (only happens on 1st of january)
if os.path.isfile(f"{ARCHIVE_PATH}{YEAR}.nc"):
    ds = xr.open_mfdataset([f"{ARCHIVE_PATH}{YEAR}.nc", f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc"], lock=False)
    if ds.time.values[-1] == ds.time.values[-2]:
        # To prevent appending to an already existing archive to the year-file
        logger.warning("Archiver was run, but the forecast time was already archived. Exiting")
        sys.exit()
else:
    ds = xr.open_mfdataset([f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc"], lock=False)

logger.debug("Writing to year file")

ds.to_netcdf(f"{ARCHIVE_PATH}{YEAR}.nc_tmp")
ds.close()
logger.debug("Done appending to year file")
os.rename(f"{ARCHIVE_PATH}{YEAR}.nc_tmp", f"{ARCHIVE_PATH}{YEAR}.nc")
