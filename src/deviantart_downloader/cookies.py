import json
from pathlib import Path

from deviantart_downloader.consts import COOKIES_FILE_PATH


def load_cookies(file_path: Path = COOKIES_FILE_PATH) -> dict[str, str]:
    """
    Loads cookies from a JSON file.

    Args:
        file_path (Path): The path to the JSON file containing cookies. Defaults
            to COOKIES_FILE_PATH.

    Returns:
        dict[str, str]: A dictionary containing cookies.
    """
    with open(file_path, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            print("Invalid JSON in cookie file.")
            return {}


def save_cookies(cookies: dict[str, str], file_path: Path = COOKIES_FILE_PATH) -> None:
    """
    Saves cookies to a JSON file.

    Args:
        cookies (dict[str, str]): A dictionary containing cookies.
        file_path (Path): The path to the JSON file to save cookies. Defaults
            to COOKIES_FILE_PATH.
    """
    with open(file_path, "w") as file:
        json.dump(cookies, file, indent=2)
