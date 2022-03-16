#    Copyright (C) 2021  Frank Thomas Tveter, Met Norway
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

import pyfimex0
import sys
import os,os.path
import math
import time
import re
import stat
import json
from glob import glob
from braceexpand import braceexpand
from datetime import datetime
from interpolator import Interpolator
from pathlib import Path


from random import random 

DEBUG=True

class Gatekeeper():
    def __init__(self,lockfile,filepattern,directory,verbose=0):
        self.start = int(round(time.time() * 1000))
        self.stamp=self.start
        self.lockfile=lockfile;
        self.pattern=filepattern;
        self.directory=directory;
        self.verbose=verbose;
        self.files=[];
        self.interpolators=[];
        self.paths=[];
        self.lats=[];
        self.lons=[];
        self.invalid=[];
        self.lock();
        if (not os.path.isdir(self.directory)):
            os.mkdir(self.directory);
        self.makeinterpolators();

    # Thanks to https://stackoverflow.com/questions/22996645/brace-expansion-in-python-glob!
    def braced_glob(self, path):
        l = []
        for x in braceexpand(path):
            l.extend(glob(x))  
        return l

    def makeinterpolators(self):
        print(self.pattern)
        files=sorted(self.braced_glob(self.pattern));
        lens=len(self.files);
        lenf=len(files)
        if DEBUG:
            print("Found %s NetCDF files from pattern %s" %(lenf, self.pattern))
        same=(lens==lenf); # only update interpolators if files have changed
        if (same): # must also check content
            ii=0;
            while (ii<lens and same):
                same=(files[ii]==self.files[ii]);
                ii=ii+1;
        if (not same): # files have changed, update interpolators...
            self.files=files;
            self.interpolators=[];
            if (self.verbose >0):
                print(self.files);
            for filename in self.files:
                ip=Interpolator(filename);
                self.interpolators.append(ip);

    def lock(self):
        if (os.path.isfile(self.lockfile)):
            if (self.file_age(self.lockfile)>10):
                os.remove(self.lockfile);
            else:
                raise Exception("Lockfile is active...");
        Path(self.lockfile).touch();

    def file_age(self,filepath): # age in seconds
        try:
            return time.time() - os.path.getmtime(filepath)
        except FileNotFoundError: # The file has been removed by another process
            return 0
        
    def collect(self):
        Path(self.lockfile).touch();
        self.paths=[];
        self.lats=[];
        self.lons=[];
        self.invalid=[];
        for filename in os.listdir(self.directory):
            path=os.path.join(self.directory, filename);
            if filename.endswith(".req"):
                if (self.verbose>1):
                    print("Request:",path);
                f=open(path,'r');
                req=f.read().replace('\n', '');
                f.close();
                os.remove(path);
                #self.invalid.append(path);
                items=req.split();
                leni=math.floor(len(items)/2);
                for ii in range(0,leni):
                    lat=items[ii*2];
                    lon=items[ii*2+1];
                    if (self.verbose>1):
                        print("   Lat:",lat," lon:",lon);
                    if (lat is not None and lon is not None):
                        self.lats.append(float(lat));
                        self.lons.append(float(lon));
                        self.paths.append(path);
            elif (filename.endswith(".res") or filename.endswith(".tmp")) and self.file_age(path) > 600:
                os.remove(path);
                #self.invalid.append(path);
                continue
            else:
                continue

    def cleanup(self):
        opath="";
        for path in self.invalid:
            if (path != opath):
                os.remove(path);
            opath=path;
            
    def process(self):
        self.collect()
        lenp=len(self.lats)
        if (lenp != 0):
            results=[]
            for interpolator in self.interpolators:
                results.append(interpolator.interpolate(self.lats,self.lons));
            leni=len(results);
            p=0;
            while (p<lenp):
                path=self.paths[p];
                outpath=path.replace(".req",".res")
                #print(result);
                #interpolator.printTime("Starting dump");
                f=open(outpath+".tmp", 'w');
                increment=False
                while(p<lenp and  path==self.paths[p]):
                    data=[];
                    i=0;
                    while (i < leni):
                        res=results[i][p]
                        data=data+res
                        i=i+1
                    str=json.dumps(data)
                    f.write(str+"\n")
                    if (self.verbose>2):
                        print("result:",str)
                    p=p+1;
                    increment=True
                f.close();
                os.rename(outpath+".tmp",outpath)
                #interpolator.printTime("Completed dump");
                #self.invalid.append(path);
                if not increment:
                    p=p+1
            self.cleanup()
                
    def printTime(self,text):
        stamp=int(round(time.time() * 1000))
        print("%d (+% 3d)"%(stamp-self.start,stamp-self.stamp),") ",text)
        self.stamp=stamp


######################################################
# start Gatekeeper and listen for requests...
######################################################

lockfile="lockfile"
#file_pattern = "{2021103100..2021110500}"
#file_pattern="%s*" % datetime.now().year
# Changing to this to automatically include data from last year's last day
file_pattern = "{%s123100..%s}" % (datetime.now().year-1,datetime.strftime(datetime.now(),"%Y%m%d%H"))
coms_path = "../coms_init"

# The default mode is "Read all data from the beginning of the season"
# If the user provides a timestamp in the format of %Y%m%d%H (e.g. 2021090100),
# an "update job" is assumed, and only the NetCDF files from that timestamp onwards
# are considered
if len(sys.argv) == 2:
    requested_time = sys.argv[1]
    coms_path = "../coms_update"
    # Check that the input is a date in this year
    try:
        if not datetime.strptime(requested_time,"%Y%m%d%H").year == datetime.now().year:
            print("ERROR: %s is not in current year. Exiting." % requested_time)
            exit(1)
    except ValueError:
        print("ERROR: Invalid datetime format: %s. Exiting." % requested_time)
        exit(1)
    file_pattern = "{%s..%s}" % (requested_time, datetime.strftime(datetime.now(),"%Y%m%d%H"))


#gk=Gatekeeper(lockfile,"../perl/outdir/all20*.nc","../coms",2)
gk=Gatekeeper(lockfile,"../perl/outdir/all%s.nc" % file_pattern,coms_path,2)

mindelay=0.1; # seconds
start=time.time()
last=start;

try:
    gk.process()
finally:
    os.remove(lockfile)

gk.printTime("Done");
