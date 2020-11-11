import pyfimex0
import os,os.path
import math
import time
import re
import stat
import json
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
                
class Interpolator():
    def __init__(self,filename,config):
        self.filename=filename;
        self.config=config;
        if (self.filename==""):
            self.filename='all.grib2';
        if (self.config==""):
            self.config='cdmGribReaderConfig.xml';
        self.minutesOfTheHour = [0]; #     
        self.undef=9.969209968386869e+36;
        self.reader = pyfimex0.createFileReader('grib2', self.filename, self.config)
        self.interpolator = pyfimex0.createInterpolator(self.reader)
        self.start = int(round(time.time() * 1000));
        self.stamp=self.start;

    def printTime(self,text):
        stamp=int(round(time.time() * 1000));
        print("%d (+% 3d)"%(stamp-self.start,stamp-self.stamp),") ",text);
        self.stamp=stamp;

    def populate(self,llen,nlen):
        ret=[];
        for ii in range(0,llen):
            line=[];
            for jj in range(0,nlen):
                line.append({});
            ret.append(line)
        return (ret);
        
    def getWindSpeed(self,u10m,v10m):
        ret=[];
        rlen=len(u10m);
        for ii in range(0,rlen):
            line=[];
            uvlen=min(len(u10m[ii]),len(v10m[ii]));
            for jj in range(0,uvlen):
                u=u10m[ii][jj];
                v=v10m[ii][jj];
                if (u != self.undef and v != self.undef):
                    #print("velocity:",u,v,u-self.undef);
                    ss=u*u+v*v;
                    ff=math.sqrt(ss);
                else:
                    ff=self.undef;
                line.append(ff); 
            ret.append(line);
        return ret;

    def getRainRate(self,time,tp):
        ret=[];
        tlen=len(time);
        for ii in range(0,tlen): # time
            line=[];
            tplen=len(tp[ii]);
            plen=len(time[ii]);
            for jj in range(0,tplen): # pos
                if (ii>0):
                    tc=time[ii][0];
                    tm=time[ii-1][0];
                    pc=tp[ii][jj];
                    pm=tp[ii-1][jj];
                    if (tc!=self.undef and tm!=self.undef and pc != self.undef and pm!= self.undef):
                        dt=max(tc-tm,1)/3600; # hours
                        dp=max(pc-pm,0);        # precipitation
                        p=dp/dt;  # precipitation/hour
                    else:
                        p=self.undef;
                else:
                    p=self.undef;
                line.append(p); 
            ret.append(line); 
        return ret;

    def getData(self,variable,index=0):
        try:
            data=self.interpolator.getDataSlice(variable,index).values();
        except:
            # we cant do anything without a time array... log error and throw error
            print ("Unable to read '",variable,"'");
            raise;
        return data;

    def assignData(self,ret,var,name):
        rlen=len(ret);
        vlen=len(var);
        for ii in range(0,vlen):
            ivar=var[ii];
            plen=len(ivar);
            if (plen==1):
                for jj in range(0,rlen):
                    if (ivar[0] != self.undef):
                        ret[jj][ii][name]=float(ivar[0]);
            else:
                for jj in range(0,plen):
                    if (ivar[jj] != self.undef):
                        ret[jj][ii][name]=float(ivar[jj]);
        return ret;

    # data is stored: ret=[<latlon1>,<latlon2>...<latlonn>], <latlon>=[<time1>...], <time>={var1:0,var2:0...}
    def interpolate(self,lats,lons):
        if (len(lats) != len(lons) or len(lats)==0):
            return [];
        self.printTime("Processing");
        ook=[0,0,0];
        orm=[0,0,0];
        self.interpolator.changeProjection(pyfimex0.InterpolationMethod.BILINEAR,
                                  lons, lats)
        self.cdm = self.interpolator.getCDM() # common data model
        self.nlen= self.cdm.getDimension('time').getLength();
        ##self.nlen=2;
        self.llen= len(lons);
        frt = self.getData('forecast_reference_time',0);
        #print("Analysis time:",frt[0]);
        self.times=[];
        self.t2m=[];
        self.rh2m=[];
        self.tp=[];
        self.u10m=[];
        self.v10m=[];
        self.lat=[];
        self.lon=[];
        for ii in range(0,self.nlen): # read data...
            try:
                times=self.getData('time',ii);
                if (times[0] != self.undef):
                    lead=(times[0]-frt[0])%3600;
                    if (lead in self.minutesOfTheHour):
                        self.times.append(times);
                        self.t2m.append(self.getData('air_temperature_2m',ii));
                        self.rh2m.append(self.getData('relative_humidity_2m',ii));
                        self.tp.append(self.getData('ga_tp_1',ii));
                        self.u10m.append(self.getData('x_wind_10m',ii));
                        self.v10m.append(self.getData('y_wind_10m',ii));
                        #self.lat.append(self.getData('latitude',ii));
                        #self.lon.append(self.getData('longitude',ii));
                        ook[2]=ook[2]+1;
                    else:
                        #print("Between-time found...",lead,times[0],frt[0]);        
                        orm[2]=orm[2]+1;
                else:
                    print("Undefined time found...");        
                ook[1]=ook[1]+1;
            except:
                print ("Unable to process time step ",ii);
                orm[1]=orm[1]+1;
                raise;
        # post process
        self.ff10m=self.getWindSpeed(self.u10m,self.v10m);
        self.rr= self.getRainRate(self.times,self.tp);
        # create output
        ret = self.populate(self.llen,len(self.times));
        self.assignData(ret,self.times,"time");
        self.assignData(ret,self.t2m,"t2m");
        self.assignData(ret,self.rh2m,"rh2m");
        #self.assignData(ret,self.tp,"tp");
        self.assignData(ret,self.rr,"rr");
        self.assignData(ret,self.ff10m,"ff10m");
        #self.assignData(ret,self.u10m,"u10m");
        #self.assignData(ret,self.v10m,"v10m");
        #self.assignData(ret,self.lat,"lat");
        #self.assignData(ret,self.lon,"lon");
        #print("Found ",ook[1]+orm[1]," times, kept ",ook[2]," (",round(100*ook[2]/(ook[1]+orm[1]),1),"%)");
        self.printTime("Done");
        return ret;


######################################################
# start Gatekeeper and listen for requests...
######################################################
lockfile="lockfile";
filename='../weather_data/all.grib2';
config='cdmGribReaderConfig.xml';
ip=Interpolator(filename,config);
gk=Gatekeeper("../coms",lockfile);
mindelay=0.1; # seconds
start=time.time();
last=start;
ip.printTime("Starting");

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
