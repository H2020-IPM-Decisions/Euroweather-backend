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
import bz2
import ftplib
import logging
import datetime
from config_and_logger import init_logging

logger = logging.getLogger(__name__)
init_logging(logger)

month_map = {"Jan": "01", "Feb": "02", "Mar": "03",
             "Apr": "04", "May": "05", "Jun": "06",
             "Jul": "07", "Aug": "08", "Sep": "09",
             "Oct": "10", "Nov": "11", "Dec": "12"}


class Poller():
    def __init__(self, ftp_username, ftp_password, ftp_account, latest_reftime=None,
                 ftp_url="opendata.dwd.de", base_ftp_link="/weather/nwp/icon-eu/grib",
                 variable_base="icon-eu_europe_regular-lat-lon_single-level_",
                 variable_list=("t_2m", "relhum_2m", "v_10m", "u_10m", "tot_prec", "asob_s"),
                 main_cycles=("00", "06", "12", "18"), max_leadtime="_078_"):
        """
        Initiates an object with ftp credentials and ftp url.

        Positional arguements:
        ftp_username -- [str]
        ftp_password -- [str]
        ftp_account -- [str]

        Keyword arguments:
        latest_reftime -- [str]
        ftp_url -- url to connect to ftp-server [str]
        variable_base -- base_filename before variable name [str]
        variable_list -- variables to look for[iterable]
        main_cycles -- main model cycles, which produce long forecasts [iterable]
        self.max_leadtime -- Last lead time for main model cycles, to check for readiness [str]
        """
        self.year = datetime.date.today().year
        self.month = datetime.date.today().month
        self.ftp_username = ftp_username
        self.ftp_password = ftp_password
        self.ftp_account = ftp_account
        self.base_ftp_link = base_ftp_link
        self.variable_base = variable_base
        self.ftp_url = ftp_url
        self.variable_list = variable_list
        self.main_cycles = main_cycles
        self.latest_reftime = latest_reftime
        self.max_leadtime = max_leadtime
        return None

    def poll(self):
        # Sets last_date to last january 1st
        last_date = datetime.datetime(self.year-1, 1, 1, 1, 1)
        # Define variables found in the iteration
        latest = None
        last_month = None
        last_day = None
        # Connect to FTP
        with ftplib.FTP(self.ftp_url, user=self.ftp_username, passwd=self.ftp_password,
                        acct=self.ftp_account) as ftp:
            ftp.cwd(self.base_ftp_link)

            # Check which reftime is newest
            run_lines = []
            # May NOT be rewritten using MLSD, no MLSD implementation on the ftp server
            ftp.retrlines("LIST", run_lines.append)

            for line in run_lines:
                # Discard parts of list that is not needed
                *_, run_name = line.split()
                # Only check run if it is main cycle
                if run_name in self.main_cycles:
                    ftp.cwd(run_name)
                    variable_lines = []
                    ftp.retrlines("LIST", variable_lines.append)
                    for line in variable_lines:
                        *_, month, day, time, name = line.split()
                        # check lai, a time-invariant variable
                        if name == "lai":
                            month = month_map[month]
                            hour, minute = time.split(":")
                            hour, minute = int(hour), int(minute)
                            new_date = datetime.datetime(self.year, int(month), int(day), hour, minute)
                            if new_date > last_date:
                                # Since last_date is always a year behind, latest will be found
                                last_date = new_date
                                last_month = month
                                last_day = day
                                latest = run_name

                    ftp.cwd("../")

            # If latest is not None, check if latest has been downloaded before
            # (if self.latest_reftime is not none)
            if latest is not None:
                reftime = str(self.year)+last_month+last_day+latest
                logger.info(f"Found newest folder to be {latest} with forecast ref {reftime}")
                if reftime == self.latest_reftime:
                    logger.info("Newest folder is already registered")
                    return reftime, False
            else:
                logger.info("Found no new folders")
                return "", False

            ftp.cwd(latest)

            ready = True
            for variable in self.variable_list:
                ftp.cwd(variable)
                last_file = self.variable_base + reftime + self.max_leadtime + variable.upper() +\
                    ".grib2.bz2"
                ready &= last_file in ftp.nlst()
                ftp.cwd("../")
                if not ready:
                    break

        return reftime, ready


class Downloader:
    def __init__(self, poller, outdir):
        self.ftp_username = poller.ftp_username
        self.ftp_password = poller.ftp_password
        self.ftp_account = poller.ftp_account
        self.ftp_url = poller.ftp_url
        self.base_ftp_link = poller.base_ftp_link
        self.variable_base = poller.variable_base
        self.variable_list = poller.variable_list
        self.main_cycles = poller.main_cycles
        self.max_leadtime = poller.max_leadtime
        self.outdir = outdir

        return None

    def download_and_unzip(self, reftime):
        refhour = reftime[-2:]
        logger.info(refhour)
        max_LT = int(self.max_leadtime.strip("_"))
        with ftplib.FTP(self.ftp_url, user=self.ftp_username, passwd=self.ftp_password,
                        acct=self.ftp_account) as ftp:
            ftp.cwd(self.base_ftp_link+"/"+refhour)
            zipped_files = []

            for variable in self.variable_list:
                ftp.cwd(variable)
                for lead_time in range(max_LT+1):
                    last_file = self.variable_base + reftime + f"_{lead_time:03d}_" +\
                        variable.upper() + ".grib2.bz2"
                    outfile = self.outdir + last_file
                    if outfile not in zipped_files:
                        ftp.retrbinary("RETR " + last_file, open(outfile, "wb+").write)
                        zipped_files.append(outfile)
                    logger.info(last_file)
                ftp.cwd("../")

        files = []
        for filepath in zipped_files:
            zipfile = bz2.BZ2File(filepath)
            data = zipfile.read()
            new_filepath = filepath[:-4]
            with open(new_filepath, 'wb') as outfile:
                outfile.write(data)
            if os.path.isfile(new_filepath):
                os.unlink(filepath)
                files.append(new_filepath)
            logger.info(f"unzipped {filepath} to {new_filepath}")

        return files, True
