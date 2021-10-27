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

# This interpolator currently works with NetCDF files collated from 
# GRIB2 files downloadedfrom DWD and MeteoFrance
# Depending on FIMEX: https://github.com/metno/fimex


import os
import pyfimex0
import math
import time # for testing

DEBUG=False

class Interpolator():
    def __init__(self,filename):
        self.start = int(round(time.time() * 1000))
        self.stamp=self.start
        self.filename=filename
        if (self.filename==""):
            self.filename='all.nc'
        self.loadFile()

    def loadFile(self):
        if(DEBUG):
            self.printTime("Loading file "+self.filename)
        self.minutesOfTheHour = [0]     
        self.undef=9.969209968386869e+36
        self.reader = pyfimex0.createFileReader('nc', self.filename)
        self.interpolator = pyfimex0.createInterpolator(self.reader)
        self.filetime=self.getFileTime(self.filename)

    def getFileTime(self,filename):
        stat = os.stat(filename)
        return stat.st_mtime

    def fileChanged(self):
        newtime=self.getFileTime(self.filename)
        return (newtime != self.filetime)

    def printTime(self,text):
        stamp=int(round(time.time() * 1000))
        print("%d (+% 3d)"%(stamp-self.start,stamp-self.stamp),") ",text)
        self.stamp=stamp

    def populate(self,llen,nlen):
        ret=[]
        for ii in range(0,llen):
            line=[]
            for jj in range(0,nlen):
                line.append({})
            ret.append(line)
        return (ret)
        
    def setWindSpeed(self):
        u10m=self.u10m
        v10m=self.v10m
        ff10m=self.ff10m
        olen=len(u10m)
        for ii in range(0,olen):
            if (ff10m[ii]==None and u10m[ii]!=None and v10m[ii]!=None):
                line=[]
                ilen=min(len(u10m[ii]),len(v10m[ii]))
                for jj in range(0,ilen):
                    line.append(self.uv2ff(u10m[ii][jj],v10m[ii][jj]))
                self.ff10m[ii]=line

    # Using total precipitation to calculate the rain rate (mm/hour)
    def setRainRate(self):
        time=self.times
        tp=self.tp
        olen=len(time) # rr is not defined
        self.rr=[None] * olen
        for ii in range(0,olen): # time
            line=[]
            if tp[ii] is not None and time[ii] is not None:
                ilen=min(len(tp[ii]),len(time[ii]))
                for jj in range(0,ilen): # pos
                    if (ii>0):
                        p=self.tp2rr(time[ii][0],time[ii-1][0],tp[ii][jj],tp[ii-1][jj])
                    else:
                        p=self.undef
                    line.append(p)
                self.rr[ii]=line

    def setHumidity(self):
        rh=self.rh2m
        t=self.t2m
        q=self.q2m
        ps=self.ps
        td=self.td2m
        olen=len(rh)
        for ii in range(0,olen): # time
            if (rh[ii]==None):
                if (q[ii]!=None and t[ii]!=None and ps[ii]!=None):
                    line=[]
                    # we have t,q and ps => rh
                    ilen=min(len(q[ii]),len(t[ii]),len(ps[ii]))
                    for jj in range(0,ilen): # pos
                        line.append(self.q2rh(q[ii][jj],t[ii][jj],ps[ii],[jj]))
                    rh[ii]=line
                elif (td[ii]!=None and t[ii]!=None):
                    line=[]
                    # we have td,t => rh
                    ilen=min(len(td[ii]),len(t[ii]))
                    for jj in range(0,ilen): # pos
                        line.append(self.td2rh(td[ii][jj],t[ii][jj]))
                    rh[ii]=line
            if (td[ii]==None):
                if (rh[ii]!=None and t[ii]!=None):
                    line=[]
                    # we have rh and t => td
                    ilen=min(len(rh[ii]),len(t[ii]))
                    for jj in range(0,ilen): # pos
                        line.append(self.rh2td(rh[ii][jj],t[ii][jj]))
                    td[ii]=line
            if (q[ii]==None):
                if (td[ii]!=None and ps[ii]!=None):
                    line=[]
                    # we have td and ps => q
                    ilen=min(len(td[ii]),len(ps[ii]))
                    for jj in range(0,ilen): # pos
                        line.append(self.ts2q(rh[ii][jj],t[ii][jj]))
                    q[ii]=line
        
    def uv2ff(self,u,v):
        #     u - u-component of wind
        #     v - v-component of wind
        # uv2ff - wind speed
        if (u != self.undef and v != self.undef):
            ss=u*u+v*v
            ff=math.sqrt(ss)
        else :
            ff=self.undef
        return ff

    def tp2rr(self,tc,tm,pc,pm):
        #      tc - time start (seconds)
        #      tm - time stop (seconds)
        #      pc - precipitation at start (mm)
        #      pm - precipitation at stop (mm)
        #   tp2rr - precipitation rate (mm/hour)
        if (tc!=self.undef and tm!=self.undef and pc != self.undef and pm!= self.undef):
            dt=max(tc-tm,1)/3600 # hours
            dp=max(pc-pm,0)        # precipitation
            p=dp/dt  # precipitation/hour
        else:
            p=self.undef
        return p

    # Compute the Specific Humidity (Bolton 1980):
    def td2q(self,td,p): # td,p
        #      Td - dew point in deg C
        #       p - pressure in mb
        #    td2q - specific humidity in g/kg.
        e= 6.112*math.exp((17.67*td)/(td + 243.5))
        q= 1000*(0.622 * e)/(p - (0.378 * e))
        return q
    
    # Compute Dew Point Temperature (Bolton 1980):
    def rh2td(self,rh,t,rice=0.0): # rh, t, ice=NULL
        #      rh - relative Humidity in percent
        #       t - temperature in deg C
        #    rice - fraction of surface ice (0..1)
        #   rh2td - dew point temperature in deg C
        ice=(rice >= 0.5 or t <= 0.0)
        es=self.satVapPres(t+273.15,ice)
        # Vapor pressure in mb:
        e =es * rh/100.0
        # Dew point in deg C
        td=math.log(e/6.112)*243.5/(17.67-math.log(e/6.112))
        return td
    
    # Compute Relative Humidity (Bolton 1980):
    def td2rh(self,td,t,rice=0.0): # td, t, ice=NULL
        #      td - dew point in deg C
        #       t - temperature in deg C
        #    rice - fraction of ice (0..1)
        #   td2rh - relative humidity (%)
        ice=(rice >= 0.5 or t <= 0.0)
        es=self.satVapPres(t+273.15, ice)
        # Vapor pressure in mb
        e=6.112*math.exp((17.67*td)/(td + 243.5))
        # Relative Humidity in percent 
        rh=100.0 * (e/es)
        if (rh>100):
            rh=100.0
        return rh
  
    #  From somewhere else... exact ENOUGH...
    def q2rh(self,q,t,p=1013.25): # q, t, p = 1013.25
        #    q - specific humidity
        #    t - temperature in Kelvin
        #    p - pressure
        # q2rh - relative humidity (%)
        es        = 6.112 * math.exp((17.67 * (t-273.15))/(t - 29.65))
        e         =q * p / (0.378 * q + 0.622)
        rh        =e / es
        if (rh > 1):
            rh=1.0
        if (rh < 0):
            rh=0.0
        return rh*100.0
  
    def satVapPres(self,t,ice=False): # t, ice
        #          t - temperature in Kelvin
        #        ice - is ice present?
        # satVapPres - saturation water vapour pressure (mb)
        if(ice):
            #    Goff Gratch equation (Smithsonian Tables, 1984):
            log10ei =  -9.09718*(273.16/t-1)-3.56654*math.log10(273.16/t)+0.876793*(1-t/273.16)+math.log10(6.1071)
            ei      =   10**log10ei
            return ei
        else:
            # Guide to Meteorological Instruments and Methods of Observation (CIMO Guide)
            tc =t - 273.15
            ew =6.112*math.exp(17.62*(tc/(243.12 + tc)))
            return ew

    def getData(self,variables,index):  # get data from alternative variables...
        for variable in variables:
            try:
                data=self.interpolator.getDataSlice(variable,index).values()
                #self.printTime ("Read '"+variable+"'")
                return data
            except:
                pass
        #self.printTime("**** Variable(s) {"+(",".join(variables))+"} not available.")
        data=None
        return data

    def assignData(self,ret,var,name):
        rlen=len(ret)
        vlen=len(var)
        for ii in range(0,vlen):
            ivar=var[ii]
            plen=0 if ivar is None else len(ivar)
            if (plen==1):
                for jj in range(0,rlen):
                    if (ivar[0] != self.undef):
                        #print(ivar[0])
                        ret[jj][ii][name]=float(ivar[0])
            else:
                for jj in range(0,plen):
                    if (ivar[jj] != self.undef):
                        ret[jj][ii][name]=float(ivar[jj])
        return ret

    # data is stored: ret=[<latlon1>,<latlon2>...<latlonn>], <latlon>=[<time1>...], <time>={var1:0,var2:0...}
    def interpolate(self,lats,lons):
        # check if file has changed even if no requests were made...
        if (self.fileChanged()):
            self.loadFile()
        if (len(lats) != len(lons) or len(lats)==0):
            return []
        if(DEBUG):
            self.printTime("Processing")
        ook=[0,0,0]
        orm=[0,0,0]
        self.interpolator.changeProjection(pyfimex0.InterpolationMethod.BILINEAR,
                                  lons, lats)
        self.cdm = self.interpolator.getCDM() # common data model
        self.nlen= self.cdm.getDimension('time').getLength()
        ##self.nlen=2
        self.llen= len(lons)
        frt = self.getData(['forecast_reference_time'],0)
        #print("Analysis time:",frt[0])
        self.times=[]
        self.ref=[]
        self.t2m=[]
        self.rh2m=[]
        self.td2m=[]
        self.q2m=[]
        self.ps=[]
        self.tp=[]
        self.u10m=[]
        self.v10m=[]
        self.ff10m=[]
        self.lat=[]
        self.lon=[]
        self.rr=[]
        for ii in range(0,self.nlen): # read data...
            try:
                times=self.getData(['time'],ii)
                if (times[0] != self.undef):
                    lead=(times[0]-frt[0])%3600
                    if (lead in self.minutesOfTheHour):
                        self.times.append(times)
                        self.ref.append(self.getData(['forecast_reference_time'],ii))
                        ###########################################################################################
                        # This is where u read data from the file and put it into variables.
                        # Names on variables may be different depending on sources.
                        # use "ncdump -h all.nc" to get a list of available variables in your file.
                        # You can list several alternative variable names in the "variable array"...
                        # ...for instance: getData(['air_temperature_2m','t2m','temperature_at_2_meter'],ii)...
                        # ...the first variable with any data will then be used...
                        # ...if no data is available for any of the alternative variables, "None" will be returned.
                        # During post-processing, the system will attempt to make missing data.
                        ###########################################################################################
                        self.t2m.append(self.getData(['air_temperature_2m'],ii))
                        self.td2m.append(self.getData(['dewpoint_temperature_2m'],ii))
                        self.rh2m.append(self.getData(['relative_humidity_2m'],ii))
                        self.q2m.append(self.getData(['specific_humidity_2m'],ii))
                        self.ps.append(self.getData(['surface_pressure'],ii))
                        self.tp.append(self.getData(['ga_tp_1'],ii)) # total precipitation
                        self.u10m.append(self.getData(['x_wind_10m'],ii))
                        self.v10m.append(self.getData(['y_wind_10m'],ii))
                        #ga_10si_103 is from MeteoFrance
                        self.ff10m.append(self.getData(['wind_speed_10m','ga_10si_103'],ii))
                        self.ps.append(self.getData(['surface_air_pressure'],ii))
                        # ga_8_1_0_1 is hourly data from MeteoFrance
                        if self.getData(["ga_8_1_0_1"],ii) is not None:
                            self.rr.append(self.getData(["ga_8_1_0_1"],ii))
                        #self.lat.append(self.getData(['latitude'],ii))
                        #self.lon.append(self.getData(['longitude'],ii))
                        ook[2]=ook[2]+1
                    else:
                        #print("Between-time found...",lead,times[0],frt[0])        
                        orm[2]=orm[2]+1
                else:
                    self.printTime("Undefined time found...")        
                ook[1]=ook[1]+1
            except:
                self.printTime("Unable to process time step ",ii)
                orm[1]=orm[1]+1
                raise
        # post process (make missing data)
        self.setWindSpeed()
        if len(self.rh2m) == 0:
            self.setHumidity()
        if len(self.rr) == 0:
            self.setRainRate()
        
        # create output
        ret = self.populate(self.llen,len(self.times))
        self.assignData(ret,self.ref,"ref")
        self.assignData(ret,self.times,"time")
        self.assignData(ret,self.t2m,"t2m")
        self.assignData(ret,self.rh2m,"rh2m")
        self.assignData(ret,self.rr,"rr")
        self.assignData(ret,self.ff10m,"ff10m")
        if(DEBUG):
            self.printTime("Done")
        return ret
