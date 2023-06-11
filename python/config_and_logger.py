import os
import yaml
import logging


def init_logging(log_obj):
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


def init_config():
    """Call to create config dictionary, if environ var CONFIGFILE not given,
    use config.yaml in the repo instead"""
    config_file = os.environ.get("CONFIGFILE", os.path.abspath(os.path.join(
        os.path.dirname(__file__), "config.yaml")))
    logger.info(f"Using config_file: {config_file}")
    with open(config_file, "r", encoding="utf8") as infile:
        CONFIG = yaml.safe_load(infile)
    return CONFIG


# Logging Setup
logger = logging.getLogger(__name__)
init_logging(logger)
