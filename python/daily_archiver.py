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
import logging
from datetime import timedelta, date
from config_and_logger import init_logging, init_config
from day_archiver import (
    accumulate_variables,
    append_daily_to_year,
    archive_day,
    write_netcdf_atomic,
)

logger = logging.getLogger(__name__)
init_logging(logger)
CONFIG = init_config()

reftime = date.today() - timedelta(days=1)
day_before = date.today() - timedelta(days=2)
reftime = reftime.strftime("%Y%m%d")
day_before = day_before.strftime("%Y%m%d")
year = reftime[:4]

ARCHIVE_PATH = CONFIG.get("archive_path")

ds = archive_day(reftime, day_before)
write_netcdf_atomic(ds, f"{ARCHIVE_PATH}daily_archive_{reftime}.nc")
ds.close()
accumulate_variables(f"{ARCHIVE_PATH}daily_archive_{reftime}.nc", f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc")

if not append_daily_to_year(
    f"{ARCHIVE_PATH}daily_accumulated_{reftime}.nc",
    f"{ARCHIVE_PATH}{year}.nc",
):
    logger.warning(
        "Archiver was run, but the forecast time was already archived"
    )
