import os
import bz2
import datetime
import ftplib

month_map = {"Jan": "01", "Feb": "02", "Mar": "03",
             "Apr": "04", "May": "05", "Jun": "06",
             "Jul": "07", "Aug": "08", "Sep": "09",
             "Oct": "10", "Nov": "11", "Dec": "12"}


# Helper methods
def newer_day(last_day, new_day):
    if int(new_day) >= int(last_day):
        return True
    return False


def newer_time(last_time, new_time):
    last_hour, last_minute = last_time.split(":")
    new_hour, new_minute = new_time.split(":")
    if int(new_hour) > int(last_hour):
        return True
    if int(new_hour) == int(last_hour):
        if int(new_minute) > int(last_minute):
            return True
    return False


class Poller():
    def __init__(self, ftp_username, ftp_password, ftp_account, latest_reftime=None,
                 ftp_url="opendata.dwd.de", base_ftp_link="/weather/nwp/icon-eu/grib",
                 variable_base="icon-eu_europe_regular-lat-lon_single-level_",
                 variable_list=("t_2m", "relhum_2m", "v_10m", "u_10m", "tot_prec"),
                 long_list=("00", "06", "12", "18"), max_leadtime="_078_"):
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
        long_list -- main model cycles, which produce long forecasts [iterable]
        max_LT -- Last lead time for main model cycles, to check for readiness [str]
        """
        self.year = datetime.date.today().year
        self.ftp_username = ftp_username
        self.ftp_password = ftp_password
        self.ftp_account = ftp_account
        self.base_ftp_link = base_ftp_link
        self.variable_base = variable_base
        self.ftp_url = ftp_url
        self.variable_list = variable_list
        self.long_list = long_list
        self.latest_reftime = latest_reftime
        self.max_leadtime = max_leadtime
        return None

    def poll(self):
        last_day = "00"
        last_time = "00:00"
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
                if run_name in self.long_list:
                    ftp.cwd(run_name)
                    variable_lines = []
                    ftp.retrlines("LIST", variable_lines.append)
                    for line in variable_lines:
                        *_, month, day, time, name = line.split()
                        # check lai, a time-invariant variable
                        if name == "lai":
                            if newer_day(last_day, day):
                                last_day = day
                                if newer_time(last_time, time):
                                    last_time = time
                                    latest_month = month_map[month]
                                    latest = run_name
                ftp.cwd("../")

            # If latest is not None, check if latest has been downloaded before (Reftime registry)
            if latest is not None:
                reftime = self.year+latest_month+last_day+latest
                print("Found newest folder to be %s with forecast ref %s" % (latest, reftime))
                if reftime == self.latest_reftime:
                    print("Newest folder is already registered")
                    return reftime, False
            else:
                print("Found no new folders")
                return "", False

            ftp.cwd(latest)

            ready = True
            for variable in self.variable_list:
                ftp.cwd(variable)
                last_file = self.variable_base + reftime + self.max_leadtime + variable.upper() + ".grib2.bz2"
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
        self.long_list = poller.long_list
        self.outdir = outdir
        return None

    def download_and_unzip(self, reftime):
        refhour = reftime[-2:]
        print(refhour)
        if refhour in self.long_list:
            max_LT = 78
        else:
            max_LT = 30

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
                    print(last_file)
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
            print(f"unzipped {filepath} to {new_filepath}")

        return files, True
