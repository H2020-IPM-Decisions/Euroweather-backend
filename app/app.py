#    Copyright (C) 2021  Tor-Einar Skog,  NIBIO
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

from flask import Flask
from flask import request
from flask import render_template
import threading
import os

from controller import Controller
from custom_errors import NoDataAvailableError

app = Flask(__name__)
controller = Controller()
sem = threading.Semaphore()

@app.route('/')
def get_forecasts():

    longitude = request.args.get("longitude", None) # WGS84
    latitude = request.args.get("latitude", None) # WGS84
    parameters = request.args.get("parameters", None) # Comma separated list
    if longitude == None or latitude == None:
        return render_template("usage.html")
    try:
        parameters = None if parameters == None else [int(i) for i in parameters.split(",")]
    except ValueError as e:
        return "BAD REQUEST: Error in specified weather parameters: %s" % e, 403
    try:
        data = controller.get_weather_data(longitude, latitude, parameters)
        return data
    except NoDataAvailableError as e:
        return "SERVICE UNAVAILABLE: Unfortunately, there is no data available at the moment.", 503
