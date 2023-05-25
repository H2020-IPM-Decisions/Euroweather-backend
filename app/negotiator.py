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

from time import sleep
import os
import os.path
import time
import threading
import json
from custom_errors import NoDataAvailableError


class Negotiator():
    def __init__(self, directory):
        self.directory = directory
        self.start = int(round(time.time() * 1000))
        self.stamp = self.start

    def printTime(self, text):
        stamp = int(round(time.time() * 1000))
        print("%d (+% 3d)" % (stamp-self.start, stamp-self.stamp), ") ", text)
        self.stamp = stamp

    def request(self, lats, lons):
        pid = threading.get_ident()
        filename = str(pid) + ".req"
        path = os.path.join(self.directory, filename)
        f = open(path+".tmp", "w")
        i = 0
        if (len(lats) == len(lons) and len(lats) > 0):
            lenl = len(lats)
            while (i < lenl):
                lat = lats[i]
                lon = lons[i]
                f.write(" "+str(lat)+" "+str(lon)+"\n")
                i = i+1
        f.close()
        os.rename(path+".tmp", path)
        outpath = path.replace(".req", ".res")
        return outpath

    def listen(self, outpath):
        patience = 30  # seconds
        start = time.time()
        current = start
        bdone = False
        while not bdone:
            sleep(0.01)
            if (os.path.isfile(outpath)):
                f = open(outpath, "r")
                res = f.read()
                f.close()
                spl = json.loads(res)
                return spl
            current = time.time()
            bdone = (current-start) > patience
        raise NoDataAvailableError
