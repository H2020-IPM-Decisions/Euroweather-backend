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
import ftplib
import logging
import datetime
import posixpath
from config_and_logger import init_logging
from icon_eu_remapper import IconEuRemapper

logger = logging.getLogger(__name__)
init_logging(logger)


class Poller():
    def __init__(self, ftp_username, ftp_password, ftp_account,
                 ftp_url="opendata.dwd.de", base_ftp_link="/weather/nwp/v1/m/icon-eu/",
                 variable_list=("t_2m", "relhum_2m", "v_10m", "u_10m", "tot_prec", "asob_s"),
                 main_cycles=("00", "06", "12", "18"), max_leadtime="_078_"):
        """
        Initiates an object with DWD connection details.

        Positional arguements:
        ftp_username -- FTP username [str]
        ftp_password -- FTP password [str]
        ftp_account -- FTP account [str]

        Keyword arguments:
        ftp_url -- DWD FTP host [str]
        base_ftp_link -- base path of the ICON-EU dataset [str]
        variable_list -- variables to look for[iterable]
        main_cycles -- main model cycles, which produce long forecasts [iterable]
        self.max_leadtime -- Last lead time for main model cycles, to check for readiness [str]
        """
        self.ftp_username = ftp_username
        self.ftp_password = ftp_password
        self.ftp_account = ftp_account
        self.base_ftp_link = base_ftp_link
        self.ftp_url = ftp_url
        self.variable_list = variable_list
        self.main_cycles = main_cycles
        self.max_leadtime = max_leadtime
        return None

    def _ftp_path(self, *parts):
        return posixpath.join(self.base_ftp_link, *parts)

    def poll(self):
        with ftplib.FTP(
            self.ftp_url,
            user=self.ftp_username,
            passwd=self.ftp_password,
            acct=self.ftp_account,
        ) as ftp:
            ftp.cwd(self._ftp_path("p", self.variable_list[0].upper(), "r"))
            runs = []
            for run_name in ftp.nlst():
                try:
                    run_time = datetime.datetime.strptime(run_name, "%Y-%m-%dT%H:%M")
                except ValueError:
                    continue
                if f"{run_time.hour:02d}" in self.main_cycles:
                    runs.append((run_time, run_name))

            if not runs:
                logger.info("Found no main-cycle forecast folders")
                return "", False

            _, latest = max(runs)
            reftime = datetime.datetime.strptime(
                latest, "%Y-%m-%dT%H:%M"
            ).strftime("%Y%m%d%H")
            logger.info(f"Found newest folder to be {latest} with forecast ref {reftime}")

            max_leadtime = int(self.max_leadtime.strip("_"))
            last_file = f"PT{max_leadtime:03d}H00M.grib2"
            ready = True
            for variable in self.variable_list:
                ftp.cwd(self._ftp_path("p", variable.upper(), "r", latest, "s"))
                variable_ready = last_file in ftp.nlst()
                ready &= variable_ready
                if not variable_ready:
                    logger.info(f"{variable} is not ready for forecast ref {reftime}")

        return reftime, ready


class Downloader:
    def __init__(
        self,
        poller,
        outdir,
        variable_base="icon-eu_europe_regular-lat-lon_single-level_",
        target_resolution=0.0625,
    ):
        self.ftp_username = poller.ftp_username
        self.ftp_password = poller.ftp_password
        self.ftp_account = poller.ftp_account
        self.ftp_url = poller.ftp_url
        self.base_ftp_link = poller.base_ftp_link
        self.variable_base = variable_base
        self.variable_list = poller.variable_list
        self.main_cycles = poller.main_cycles
        self.max_leadtime = poller.max_leadtime
        self.outdir = outdir
        self.target_resolution = target_resolution

        return None

    def download_and_unzip(self, reftime):
        run_time = datetime.datetime.strptime(reftime, "%Y%m%d%H")
        run_name = run_time.strftime("%Y-%m-%dT%H:00")
        max_leadtime = int(self.max_leadtime.strip("_"))
        files = []
        coordinate_paths = {
            variable: os.path.join(
                self.outdir, f"icon-eu_{reftime}_{variable}.grib2"
            )
            for variable in ("CLAT", "CLON")
        }
        with ftplib.FTP(
            self.ftp_url,
            user=self.ftp_username,
            passwd=self.ftp_password,
            acct=self.ftp_account,
        ) as ftp:
            try:
                for variable, coordinate_path in coordinate_paths.items():
                    ftp.cwd(
                        posixpath.join(
                            self.base_ftp_link, "p", variable, "r", run_name, "s"
                        )
                    )
                    with open(coordinate_path, "wb") as outfile:
                        ftp.retrbinary("RETR PT000H00M.grib2", outfile.write)

                remapper = IconEuRemapper(
                    coordinate_paths["CLAT"],
                    coordinate_paths["CLON"],
                    self.outdir,
                    self.target_resolution,
                )
                for variable in self.variable_list:
                    ftp.cwd(
                        posixpath.join(
                            self.base_ftp_link,
                            "p",
                            variable.upper(),
                            "r",
                            run_name,
                            "s",
                        )
                    )
                    for lead_time in range(max_leadtime + 1):
                        remote_file = f"PT{lead_time:03d}H00M.grib2"
                        local_file = (
                            self.variable_base + reftime + f"_{lead_time:03d}_"
                            + variable.upper() + ".grib2"
                        )
                        filepath = os.path.join(self.outdir, local_file)
                        unstructured_path = f"{filepath}.unstructured"
                        try:
                            with open(unstructured_path, "wb") as outfile:
                                ftp.retrbinary(f"RETR {remote_file}", outfile.write)
                            remapper.remap(unstructured_path, filepath)
                        finally:
                            if os.path.isfile(unstructured_path):
                                os.unlink(unstructured_path)
                        files.append(filepath)
                        logger.info(
                            f"Downloaded and remapped {remote_file} to {filepath}"
                        )
            finally:
                for coordinate_path in coordinate_paths.values():
                    if os.path.isfile(coordinate_path):
                        os.unlink(coordinate_path)

        return files, True
