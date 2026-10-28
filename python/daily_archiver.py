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
import argparse
import logging
import os
from datetime import timedelta, date, datetime
from config_and_logger import init_logging, init_config
from day_archiver import (
    accumulate_variables,
    append_daily_to_year,
    archive_day,
    available_cycle_paths,
    daterange,
    IncompleteDayError,
)

logger = logging.getLogger(__name__)
init_logging(logger)
CONFIG = init_config()

ARCHIVE_PATH = CONFIG.get("archive_path")


def archive_date(target_date):
    reftime = target_date.strftime("%Y%m%d")
    day_before = (target_date - timedelta(days=1)).strftime("%Y%m%d")
    if not (
        available_cycle_paths(day_before) or available_cycle_paths(reftime)
    ):
        logger.warning("Skipping %s: no source forecasts found", reftime)
        return

    daily_path = os.path.join(ARCHIVE_PATH, f"daily_archive_{reftime}.nc")
    accumulated_path = os.path.join(ARCHIVE_PATH, f"daily_accumulated_{reftime}.nc")
    try:
        archive_day(reftime, day_before, output_path=daily_path)
    except IncompleteDayError as error:
        logger.warning("Skipping %s: %s", reftime, error)
        return

    accumulate_variables(daily_path, accumulated_path)
    if not append_daily_to_year(
        accumulated_path,
        os.path.join(ARCHIVE_PATH, f"{target_date.year}.nc"),
    ):
        logger.warning("Date %s was already present in the yearly archive", reftime)
    else:
        logger.info("Archived %s", reftime)


def parse_date(value):
    try:
        parsed = datetime.strptime(value, "%Y%m%d").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError("Dates must use YYYYMMDD") from error
    if parsed.strftime("%Y%m%d") != value:
        raise argparse.ArgumentTypeError("Dates must use YYYYMMDD")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Archive yesterday, or every complete day in an inclusive date range."
    )
    parser.add_argument("start_date", nargs="?", type=parse_date, help="YYYYMMDD")
    parser.add_argument("end_date", nargs="?", type=parse_date, help="YYYYMMDD (inclusive)")
    args = parser.parse_args(argv)
    if (args.start_date is None) != (args.end_date is None):
        parser.error("Provide both start_date and end_date, or neither")
    start_date = args.start_date or date.today() - timedelta(days=1)
    end_date = args.end_date or start_date
    if end_date < start_date:
        parser.error("end_date must not precede start_date")

    for target_date in daterange(start_date, end_date):
        archive_date(target_date)
    archive_date(end_date)


if __name__ == "__main__":
    main()
