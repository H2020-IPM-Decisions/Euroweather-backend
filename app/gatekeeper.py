import pyfimex0
import os,os.path
import math
import time
import re
import stat
import json
from interpolator import Interpolator
from pathlib import Path


from random import random 

class Gatekeeper():
    def __init__(self,directory,lockfile):
        self.directory=directory;
        self.lockfile=lockfile;
        self.paths=[];
        self.lats=[];
        self.lons=[];
        self.invalid=[];
        if (not os.path.isdir(self.directory)):
            os.mkdir(self.directory);
        self.lock();

    def lock(self):
        if (os.path.isfile(self.lockfile)):
            if (self.file_age(self.lockfile)>10):
                os.remove(lockfile);
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
                print(path);
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
                    print("Lat:",lat," lon:",lon);
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
        
            
    def process(self,interpolator):
        self.collect();
        results=interpolator.interpolate(self.lats,self.lons);
        i=0;
        lenr=len(results);
        while (i< lenr):
            path=self.paths[i];
            outpath=path.replace(".req",".res");
            #print(result);
            #interpolator.printTime("Starting dump");
            f=open(outpath+".tmp", 'w');
            increment=False;
            while (i<lenr and  path==self.paths[i]):
                   result=results[i];
                   str=json.dumps(result);
                   f.write(str+"\n");
                   i=i+1;
                   increment=True;
            f.close();
            os.rename(outpath+".tmp",outpath);
            #interpolator.printTime("Completed dump");
            #self.invalid.append(path);
            if not increment:
                i=i+1;
        self.cleanup();
                

######################################################
# start Gatekeeper and listen for requests...
######################################################
lockfile="lockfile";
filename='../weather_data/all.nc';
#config='cdmGribReaderConfig.xml';
ip=Interpolator(filename);
gk=Gatekeeper("../coms",lockfile);
mindelay=0.1; # seconds
start=time.time();
last=start;
ip.printTime("Starting");

## Running it for one hour
try:
    while(last - start < 3600):
        gk.process(ip);
        current=time.time();
        delay=last+mindelay-current;
        if (delay>0):
            time.sleep(delay);
        last=current;
finally:
    os.remove(lockfile);
    ip.printTime("Terminating");

ip.printTime("Done");
