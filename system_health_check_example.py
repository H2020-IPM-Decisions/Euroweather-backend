#!/usr/bin/python3

#    Copyright (C) 2021-2024  Tor-Einar Skog, NIBIO
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.


# Health check of the system. 
#
# Usage: Run from the console. Returns 1 if everything is OK, 0 otherwise

import os
import sys
import glob
import psutil
import netCDF4 as nc
from datetime import datetime, timezone, timedelta
from typing import List

from smtplib import SMTP
from email.mime.text import MIMEText

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

# Set this to True if you want to receive email notifications on system.exit(1)
SEND_EMAIL_ALERT = True
EMAIL_RECIPIENT = "foobar@test.com"
EMAIL_SENDER = "barfoo@test.com"
SMTP_HOST = "smtp.foo.bar"
DATA_DIR_RELATIVE_PATH = "/python/outdir/"

DEBUG = False

error_msg = []
exit_code = 0

############# Method definitions #################

def get_most_recent_file(file_expr: str) -> str:
    """Returns the path/name of the most recent file following the file_expr pattern"""
    glob_expr = file_expr % "*"
    nc_files = glob.glob(f"{SITE_ROOT}{DATA_DIR_RELATIVE_PATH}{glob_expr}")
    most_recent_file = ""
    for nc_file in nc_files:
        nc_file = os.path.basename(nc_file) 
        most_recent_file = nc_file if nc_file > most_recent_file else most_recent_file
    return f"{SITE_ROOT}{DATA_DIR_RELATIVE_PATH}{most_recent_file}"

def check_recent_file(file_expr: str, timestamp_expr: str, hours_delta: int):
    """Checks that the most recent file is no older than now - hours_delta. Assuming timestamps in file names are on form YYYYMMDD[HH] <= HH is optional"""
    global error_msg, exit_code
    # Check how recent the .nc-files in python/outdir are
    most_recent_file = os.path.basename(get_most_recent_file(file_expr))
    # Get the date stamp for now - 12 h, create a "allYYYYmmddhh.nc" filename and compare
    threshold_filename=f"{file_expr}" % datetime.strftime(datetime.now(timezone.utc) + timedelta(hours=hours_delta),timestamp_expr)

    if DEBUG:
        glob_expr = file_expr % "*"
        print(f"{SITE_ROOT}{DATA_DIR_RELATIVE_PATH}{glob_expr}")
        print("%s %s" %(most_recent_file,threshold_filename))
    
    if threshold_filename >= most_recent_file:
        exit_code = 1
        error_msg.append(f"The latest NetCDF file {most_recent_file} is out of date")

def check_most_recent_file_contents(file_expr: str, expected_time_steps: int, expected_params: List[str]):
    """Checks that the most recent file contains the expected number of time steps and contains the expected parameters"""
    global error_msg, exit_code
    most_recent_file = get_most_recent_file(file_expr)
    dataset_metadata = nc.Dataset(f"{most_recent_file}", "r")
    timesteps = dataset_metadata.variables["time"][:]
    if len(timesteps) != expected_time_steps:
        exit_code = 1
        error_msg.append(f"The latest NetCDF file {most_recent_file} contains {len(timesteps)} timesteps, but we expected {expected_time_steps}")
    param_names = dataset_metadata.variables.keys()
    for expected_param in expected_params:
        if expected_param not in param_names:
            exit_code = 1
            error_msg.append(f"Parameter {expected_param} missing in {most_recent_file}")

############### System checks ####################

# The latest allYYYYMMDDHH.nc should not be older than 12 hours
check_recent_file("all%s.nc", "%Y%m%d%H", -12)
# The latest allYYYYMMDDHH.nc should contain 79 timesteps and the parameters listed
check_most_recent_file_contents("all%s.nc", 79,['relative_humidity_2m', 'total_precipitation', 'air_temperature_2m', 'x_wind_10m', 'y_wind_10m', 'hourly_precipitation', 'wind_speed_10m'])

# The latest daily_archive_YYYYMMDD.nc should not be older than from tomorrow
check_recent_file("daily_archive_%s.nc", "%Y%m%d", 24)
# The latest daily_archive_YYYYMMDD.nc should contain 24 timesteps and the parameters listed
check_most_recent_file_contents("daily_archive_%s.nc", 24,['relative_humidity_2m', 'air_temperature_2m', 'hourly_precipitation', 'wind_speed_10m'])

# The latest daily_accumulated_YYYYMMDD.nc should not be older than from tomorrow
check_recent_file("daily_accumulated_%s.nc", "%Y%m%d", 24)
# The latest daily_accumulated_YYYYMMDD.nc should contain one timestemp and the parameters listed
check_most_recent_file_contents("daily_accumulated_%s.nc", 1,['air_temperature_2m_max', 'air_temperature_2m_min', 'air_temperature_2m_mean', 'relative_humidity_2m_mean', 'relative_humidity_2m_max', 'total_precipitation', 'mean_wind_speed_10m'])

# When only DISK_LIMIT_GB left on disk, alert
DISK_LIMIT_GB = 400 # 400 GB is a little over a month's worth of files
free_space = round(psutil.disk_usage(f"{SITE_ROOT}{DATA_DIR_RELATIVE_PATH}").free / 1073741824, 1) # 1073741824 bytes = 1 Gb

if(free_space < DISK_LIMIT_GB):
    exit_code = 1
    error_msg.append(f"Warning: There is only {free_space} GB left on the data disk.")

if(DEBUG):
    print("\n".join(error_msg))


################# Alerts/notifications ################

if exit_code != 0 and SEND_EMAIL_ALERT:
    if DEBUG:
        print("Sending email")
    msg = MIMEText("\n".join(error_msg),"plain")
    msg["Subject"] = "Euroweather-backend ALERT: NetCDF files are out of date"
    msg["From"] = EMAIL_SENDER
    conn = SMTP(SMTP_HOST)
    conn.set_debuglevel(False)
    try:
        conn.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
    finally:
        conn.quit()

print("System check %s" % ("OK" if exit_code == 0 else "FAILED"))

sys.exit(exit_code)