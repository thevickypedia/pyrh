"""This module contains the caching logic for Robinhood login data."""

import pathlib
import pickle
import time
from datetime import datetime
from typing import Union

from pyrh.exceptions import InvalidCacheFile

from .oauth import OAuth, OAuthSchema

LOGIN_ROOT: pathlib.Path = pathlib.Path("~/.robinhood").expanduser()
"""The root directory where the login tokens are stored.

Creates the directory on import.
"""
LOGIN_ROOT.mkdir(parents=True, exist_ok=True)

LOGIN_FILE: pathlib.Path = LOGIN_ROOT.joinpath("login.pickle")
"""Path to login.pickle file.

Creates the file on import.
"""
LOGIN_FILE.touch(exist_ok=True)


def load_existing_oauth() -> Union[OAuth, None]:
    """Get the path to the login file."""
    try:
        with LOGIN_FILE.open("rb") as file:
            json_data = pickle.load(file)
        assert isinstance(json_data, dict), "Cached data must be a dictionary."
        assert json_data.get("login"), "Cached data must contain 'login' key."
        assert json_data.get("expiry"), "Cached data must contain 'expiry' key."
        assert isinstance(json_data["expiry"], int), "'expiry' must be an integer."
        if json_data["expiry"] < int(time.time()):
            print("Cached login data has expired.")
            return None
        assert isinstance(json_data["login"], dict), "'login' must be a dictionary."
    except AssertionError as error:
        print(f"Invalid cached data: {error}")
        raise InvalidCacheFile("Cached login file is invalid or corrupted.")
    except (FileNotFoundError, EOFError):
        return None
    else:
        return OAuthSchema().load(json_data["login"])


def save_existing_oauth(data: OAuth) -> None:
    """Save the login data to the login file."""
    expiry = int(time.time()) + data.expires_in
    expiration_dt = datetime.fromtimestamp(expiry).isoformat()
    login_data = {
        "login": data.__dict__,
        "expiry": expiry,
        "expiration_dt": expiration_dt,
    }
    with LOGIN_FILE.open("wb") as file:
        pickle.dump(login_data, file)
    print(f"Login data saved to {LOGIN_FILE} valid until {expiration_dt}.")
