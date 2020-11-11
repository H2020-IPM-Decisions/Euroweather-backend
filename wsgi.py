import sys
import os

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0,SITE_ROOT + '/app')

from app import app as application

