"""
    Copyright (C) 2023  Johannes Tobiassen Langvatn, Met Norway

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import logging


def _init_logging(log_obj):
    """Call to initialise logging."""
    # Read environment variables
    want_level = os.environ.get("LOGLEVEL", "INFO")
    log_file = os.environ.get("LOGFILE", None)

    # Determine log level and format
    if hasattr(logging, want_level):
        log_level = getattr(logging, want_level)
    else:
        print("Invalid logging level '%s' in environment variable LOGLEVEL" % want_level)
        log_level = logging.INFO

    if log_level < logging.INFO:
        msg_format = "[{asctime:}] {name:>28}:{lineno:<4d} {levelname:8s} {message:}"
    else:
        msg_format = "{levelname:8s} {message:}"

    log_format = logging.Formatter(fmt=msg_format, style="{")
    log_obj.setLevel(log_level)

    # Create stream handlers
    h_stdout = logging.StreamHandler()
    h_stdout.setLevel(log_level)
    h_stdout.setFormatter(log_format)
    log_obj.addHandler(h_stdout)

    if log_file is not None:
        h_file = logging.FileHandler(log_file, encoding="utf-8")
        h_file.setLevel(log_level)
        h_file.setFormatter(log_format)
        log_obj.addHandler(h_file)

    return


logger = logging.getLogger(__name__)
_init_logging(logger)
