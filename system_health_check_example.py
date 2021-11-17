#!/usr/bin/python3

#    Copyright (C) 2021  Tor-Einar Skog, NIBIO
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


# Health check of the system. Currently, the only check is that
# * The latest NetCDF file is from a model run maximum 12 hours ago
#
# Usage: 
# * Copy this example file to "system_health_check.py", make adjustments and run from the console. 
# * Returns 1 if everything is OK, 0 otherwise

import os
import sys
import glob
from datetime import datetime, timezone, timedelta

from smtplib import SMTP
from email.mime.text import MIMEText

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

# Set this to True if you want to receive email notifications on system.exit(1)
SEND_EMAIL_ALERT = False
EMAIL_RECIPIENT = "foo@bar.com"
EMAIL_SENDER = "noreply@bar.com"
SMTP_HOST = "mail.bar.com"

DEBUG = False

# Check how recent the .nc-files in perl/outdir are
nc_files = glob.glob(SITE_ROOT + "/perl/outdir/*.nc")
most_recent_file = ""
for nc_file in nc_files:
    nc_file = os.path.basename(nc_file) 
    most_recent_file = nc_file if nc_file > most_recent_file else most_recent_file

# Get the date stamp for now - 12 h, create a "allYYYYmmddhh.nc" filename and compare
threshold_filename="all%s.nc" % datetime.strftime(datetime.now(timezone.utc) - timedelta(hours=12),"%Y%m%d%H")

if DEBUG:
    print("%s %s" %(most_recent_file,threshold_filename))

exit_code = 0 if threshold_filename < most_recent_file else 1

if exit_code != 0 and SEND_EMAIL_ALERT:
    if DEBUG:
        print("Sending email")
    msg = MIMEText("The latest NetCDF file %s is out of date" % most_recent_file,"plain")
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