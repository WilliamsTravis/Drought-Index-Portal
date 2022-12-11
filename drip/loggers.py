# -*- coding: utf-8 -*-
"""Logginf functions.

Created on Sat Mar  5 15:14:47 2022

@author: travis
"""
import functools
import inspect
import logging

from pathlib import Path

import dash

logger = logging.getLogger(__name__)


MSG_FMT = "%(levelname)s - %(asctime)s [%(filename)s:%(lineno)d] : %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"
LOG_LEVELS = {
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}


def callback_trigger():
    """Get the callback trigger, if it exists.

    Returns
    -------
    str
        String representation of callback trigger, or "Unknown" if
        context not found.
    """
    try:
        trigger = dash.callback_context.triggered[0]["prop_id"]
        trigger_value = dash.callback_context.triggered[0]["value"]
    except dash.exceptions.MissingCallbackContextException:
        trigger = "Unknown"
        trigger_value = "Unknown"

    return trigger, trigger_value


def init_logger(name, level="DEBUG", mode="w"):
    """Initialize a basic logger object.

    Paramters
    ---------
    level : str
        Logging level to use. Must be 'INFO', 'DEBUG', 'WARNING', 'ERROR', or
        'CRITICAL'.
    filename : str
        Path to file in which to write logging information. If None, will
        default to the name of the logger.

    Returns
    -------
    logger:  logging.Logger
        Log object.
    """
    logging.basicConfig(
        format=MSG_FMT,
        filename="/dev/null",
        level=LOG_LEVELS[level],
        datefmt=DATE_FMT,
        filemode=mode
    )
    logger = logging.getLogger(name)
    return logger


def set_handler(logger, filename, level="DEBUG"):
    """Add file handler to logging object."""
    for handler in logger.handlers:
        logger.removeHandler(handler)
    Path(filename).parent.mkdir(exist_ok=True)
    formatter = logging.Formatter(MSG_FMT, DATE_FMT)
    handler = logging.FileHandler(filename, "w")
    handler.setFormatter(formatter)
    handler.setLevel(LOG_LEVELS[level])
    logger.addHandler(handler)


class AppLogger():
    """Class for handling retrieving function arguments."""

    def __init__(self):
        """Initialize Logger object."""
        self.args = {}

    def __repr__(self):
        """Return Logger representation string."""
        attrs = ", ".join([f"{k}={v}" for k, v in self.__dict__.items()
                           if k != "args"])
        n = len(self.args.keys())
        msg = f"<Logger: {attrs} {n} function argument dicts>"
        return msg

    @property
    def getall(self):
        """Return executable variable setters for all callbacks."""
        set_pairs = []
        for func, args in self.args.items():
            for key, arg in args.items():
                if isinstance(arg, str):
                    set_pairs.append(f"{key}='{arg}'")
                else:
                    set_pairs.append(f"{key}={arg}")
        cmd = "; ".join(set_pairs)
        return cmd

    def getargs(self, func_name):
        """Return executable variable setters for one callback."""
        set_pairs = []
        args = self.args[func_name]
        for key, arg in args.items():
            if isinstance(arg, str):
                set_pairs.append(f"{key}='{arg}'")
            else:
                set_pairs.append(f"{key}={arg}")
        cmd = "; ".join(set_pairs)
        return cmd

    def printall(self):
        """Print all kwargs for each callback in executable fashion."""
        for func, args in self.args.items():
            for key, arg in args.items():
                if isinstance(arg, str):
                    print(f"{key}='{arg}'")
                else:
                    print(f"{key}={arg}")

    def setargs(self, **kwargs):
        """Log the most recent arguments of a callback."""
        caller = inspect.stack()[1][3]
        print(f"Running {caller}...")
        self.args[caller] = kwargs



class CallbackArgs:
    """Class for handling logs and retrieving callback function arguments."""

    def __init__(self):
        """Initialize CallbackArgs object."""
        self.args = {}

    def __repr__(self):
        """Return FunctionCalls representation string."""
        name = self.__class__.__name__
        msg = f"<{name} object: {len(self.args)} callbacks.>"
        return msg

    def print_all(self):
        """Print all kwargs for each callback in executable fashion."""
        for args in self.args.values():
            for key, arg in args.items():
                print(f"{key}={arg!r}")

    @property
    def all(self):
        """Return executable variable setters for all callbacks.
        The purpose of this function is to compile a string that
        can be used as input to `exec` that sets all the input
        arguments all callbacks as actual variables in your
        namespace. Note that some overlap may occur.

        Returns
        -------
        str
            A string that can be used as input to `exec` that sets all
            the input arguments all callbacks as actual variables in
            your namespace.

        Notes
        -----
        See `FunctionCalls.get` documentation for example(s).
        """
        return "; ".join([f"{key}={arg!r}" for key, arg in self.args.items()])

    def __call__(self, func_name):
        """Return executable variable setters for one callback.
        
        The purpose of this function is to compile a string that can be used as
        input to  `exec` that sets all the input arguments to the function
        `func_name` as actual variables in your namespace.

        Parameters
        ----------
        func_name : str
            Name of function to obtain arguments for,
            represented as a string.
    
        Returns
        -------
        str
            A string that can be used as input to `exec` that sets all
            the input arguments to the function as actual variables in
            your namespace.
    
        Examples
        --------
        >>> calls('options_chart_tabs')
        "tab_choice='chart'; chart_choice='cumsum'"
        """
        args = self.args.get(func_name, {})
        args_str = "; ".join([f"{key}={arg!r}" for key, arg in args.items()])
        return args_str

    def log(self, func):
        """Log the function call.

        Allow extra logging with the `verbose` argument.

        Parameters
        ----------
        verbose : bool, optional
            Specify whether to log the function is call itself,
            by default False.
        """
        @functools.wraps(func)
        def _callback_func(*args, **kwargs):
            """Store the arguments used to call the function."""
            name = func.__name__
            sig = inspect.signature(func)
            keys = sig.parameters.keys()

            trigger, trigger_value = callback_trigger()

            self.args[name] = {
                **dict(zip(keys, args)),
                **kwargs,
                "trigger": trigger,
                "trigger_value": trigger_value
            }

            logger.info("Running %s... (Trigger: %s)", name, trigger)
            logger.debug("Args: %s", self(name))

            return func(*args, **kwargs)

        return _callback_func
