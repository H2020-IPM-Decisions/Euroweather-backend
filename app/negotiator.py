from time import sleep
import pyfimex0
import os, os.path
import math
import time
from random import random 
import threading
import json

class Negotiator():
    def __init__(self,directory):
        self.directory=directory;
        self.start = int(round(time.time() * 1000));
        self.stamp=self.start;

    def printTime(self,text):
        stamp=int(round(time.time() * 1000));
        print("%d (+% 3d)"%(stamp-self.start,stamp-self.stamp),") ",text);
        self.stamp=stamp;

    def request(self,lats,lons):
        #pid=os.getpid();
        pid=threading.get_ident()
        filename=str(pid) + ".req";
        path=os.path.join(self.directory, filename);
        f=open(path+".tmp", "w");
        i=0;
        if (len(lats) == len(lons) and len(lats)>0):
            lenl=len(lats);
            while (i<lenl):
                lat=lats[i];
                lon=lons[i];
                f.write(" "+str(lat)+" "+str(lon)+"\n");
                i=i+1;
        f.close();
        os.rename(path+".tmp",path);
        outpath=path.replace(".req",".res");
        return outpath

    def listen(self,outpath):
        patience=30;    # seconds
        start=time.time();
        current=start;
        bdone=False;
        while (not bdone):
            sleep(0.01)
            if (os.path.isfile(outpath)):
                f=open(outpath,"r");
                res=f.read();
                f.close();
                #print(outpath+" :> "+res);
                spl=json.loads(res)#.split("\n");
                os.remove(outpath);
                return spl;
            current=time.time();
            bdone=(current-start) > patience;
        return [];


######################################################
# Send one request and listen for reply...
######################################################
"""
directory="./coms";
negotiator=Negotiator(directory);
path=negotiator.request([50.0,50.1],[11.0,11.1]);
ret=negotiator.listen(path);
print(ret);
"""