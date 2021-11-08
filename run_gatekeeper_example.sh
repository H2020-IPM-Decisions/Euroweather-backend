#!/bin/bash

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


# Use this as a template for building your server
# specific rsync script to sync the coms_* folders
# between the Euroweather-frontend and Euroweather-backend
# and running the gatekeeper to produce the results

BACKEND_HOME=/home/nibio/Euroweather-backend
FRONTEND_HOME=[YOUR FRONTEND PATH HERE]

cd $BACKEND_HOME/app
#### INIT JOB
# Retreive req files from frontend
rsync -a --delete $FRONTEND_HOME/coms_init/ $BACKEND_HOME/coms_init/
# Run INIT jobs
python3 gatekeeper.py
# Sync results to frontend
rsync -a --delete $BACKEND_HOME/coms_init/ $FRONTEND_HOME/coms_init/


#### UPDATE JOB
# Retreive req files from frontend
rsync -a --delete $FRONTEND_HOME/coms_update/ $BACKEND_HOME/coms_update/
# Run UPDATE jobs
python3 gatekeeper.py $(date --date="yesterday" +"%Y%m%d00")
# Sync results to frontend
rsync -a --delete $BACKEND_HOME/coms_update/ $FRONTEND_HOME/coms_update/