#!/usr/bin/python3

# Deletes raw data from last year

import subprocess
from datetime import datetime



year=2024
if datetime.now().year == year:
    print("WARNING: You are trying to delete files form current year. Aborting.")
    exit(0)

# grib2 files in the grib folder. Raw data downloaded from DWD OpenData
# Need to loop because there are too many files for one run of rm
params=["RELHUM_2M","TOT_PREC","T_2M","U_10M","V_10M"]
#params=["RELHUM_2M"]

for month_index in range(1,13):
    month = str(month_index).zfill(2)
    for param in params:
        print(f"rm outdir/grib/*{year}{month}*{param}.grib2")
        subprocess.run(f"rm outdir/grib/*{year}{month}*{param}.grib2", shell=True)