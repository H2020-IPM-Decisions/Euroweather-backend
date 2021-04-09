from flask import Flask
from flask import request
from flask import render_template
import threading
import os

from controller import Controller

#os.environ["FIMEX_CHUNK_CACHE_SIZE"] = "218523238400" # TEST: See if this affects performance
app = Flask(__name__)
controller = Controller()
sem = threading.Semaphore()

@app.route('/')
def get_forecasts():
    #sem.acquire()
    #print("Thread_ident: %s" % str(threading.get_ident()));
    #print("get_forecasts() called")
    longitude = request.args.get("longitude", None) # WGS84
    latitude = request.args.get("latitude", None) # WGS84
    parameters = request.args.get("parameters", None) # Comma separated list
    if longitude == None or latitude == None:
        return "BAD REQUEST: Missing longitude and/or latitude", 403
    try:
        parameters = None if parameters == None else [int(i) for i in parameters.split(",")]
    except ValueError as e:
        return "BAD REQUEST: Error in specified weather parameters: %s" % e, 403
    
    #controller = Controller()
    data = controller.get_weather_data(longitude, latitude, parameters)
    #sem.release()

    return data
    #print(parameters)
