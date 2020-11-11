import pyfimex0
import os.path
import math
import time # for testing

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
                    ret[jj][ii][name]=ivar[0];
            else:
                for jj in range(0,plen):
                    ret[jj][ii][name]=ivar[jj];
        return ret;

    # data is stored: ret=[<latlon1>,<latlon2>...<latlonn>], <latlon>=[<time1>...], <time>={var1:0,var2:0...}
    def interpolate(self,lats,lons):
        ook=[0,0,0];
        orm=[0,0,0];
        start_time = time.time() ## REMOVE WHEN DONE WITH DEBUG
        self.interpolator.changeProjection(pyfimex0.InterpolationMethod.BILINEAR,
                                  lons, lats)
        change_p_time = time.time()## REMOVE WHEN DONE WITH DEBUG
        self.cdm = self.interpolator.getCDM() # common data model
        cdm_time = time.time()## REMOVE WHEN DONE WITH DEBUG
        self.nlen= self.cdm.getDimension('time').getLength();
        get_time_time = time.time()## REMOVE WHEN DONE WITH DEBUG
        
        ##self.nlen=2;
        self.llen= len(lons);
        frt = self.getData('forecast_reference_time',0);
        get_data_ref_time = time.time()## REMOVE WHEN DONE WITH DEBUG
        
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
        pre_post_process_time = time.time()
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
        print("Found ",ook[1]+orm[1]," times, kept ",ook[2]," (",round(100*ook[2]/(ook[1]+orm[1]),1),"%)");
        prepare_data_time = time.time()## REMOVE WHEN DONE WITH DEBUG
        ## REMOVE WHEN DONE WITH DEBUG
        print("Change p took %s seconds, getCDM took % seconds, getTimeDim took %s seconds, getDataRefTime took %s seconds, getWeatherData took %s seconds, prepare data took % seconds" %(
                    change_p_time - start_time,
                    cdm_time - change_p_time,
                    get_time_time - cdm_time,
                    get_data_ref_time - get_time_time,
                    pre_post_process_time - get_data_ref_time,
                    prepare_data_time - pre_post_process_time
        ))
        return ret;

"""filename='../weather_data/all.grib2';
config='cdmGribReaderConfig.xml';
ip=Interpolator(filename,config);

lats = [50.109, 50.052, 50.0];
lons = [10.965, 10.13, 10.5];
lats=[50.109];
lons = [10.965];
res=ip.interpolate(lats,lons);
print("Results:",res);
"""
