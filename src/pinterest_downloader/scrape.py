import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from bs4.element import NavigableString, ResultSet, Tag
from fake_useragent import UserAgent
from requests import Response, Session, get
from requests_pprint import print_response_summary
from rich import print

from pinterest_downloader.consts import DOWNLOAD_PATH, MAX_GALLERY_ITEMS

ua = UserAgent(min_version=120.0)
_user_agent: str = ""


def get_user_agent() -> str:
    global _user_agent

    if _user_agent == "":
        _user_agent = ua.random
    return _user_agent


def send_request(*, session: Session, **kwargs: Any) -> Optional[Response]:
    """
    Sends a GET request to the specified URL with the given headers and
    session. If the response is not OK, it prints the response summary and
    exits the program.

    Args:
        session (requests.Session): The requests session to use.
        **kwargs: Additional keyword arguments like 'url', 'headers', etc.

    Returns:
        Optional[requests.Response]: The response if successful, else None.
    """
    response: Response = session.get(**kwargs)
    if not response.ok:
        print_response_summary(response)
        return None

    if "Set-Cookie" in response.headers:
        # Check if the session cookie auth has been deleted
        if "auth=deleted" in response.headers["Set-Cookie"]:
            print("Session cookies have been deleted. Please log in again.")
            return None

        print("Session cookies have changed. Sending request again...")
        # Retry the request with updated cookies
        return send_request(session=session, **kwargs)

    return response


def extract_image_url(html: str, class_list: list[str]) -> Optional[str]:
    """
    Extracts the image URL from the HTML content using BeautifulSoup.

    Args:
        html (str): The HTML content to parse.
        class_list (list[str]): The list of classes to search for.

    Returns:
        Optional[str]: The extracted image URL, or None if not found.
    """
    # Parse the HTML content to find the image URL
    soup = BeautifulSoup(html, "html.parser")
    img_class: list[str] = ["TZM0T", "_2NIJr"]
    img_tag: Tag | NavigableString | None = soup.find("img", class_=class_list)
    if img_tag is None or isinstance(img_tag, NavigableString):
        print(f"Image with class {img_class} not found.")
        return None

    img_url: str | list[str] = img_tag["src"]
    if isinstance(img_url, list):
        img_url = img_url[0]

    return img_url


def extract_artist_name(url: str) -> str:
    """
    Extracts the artist name from the URL.

    Args:
        url (str): The URL to extract the artist name from.

    Returns:
        str: The extracted artist name.
    """
    path_parts: list[str] = urlparse(url).path.strip("/").split("/")
    return path_parts[0] if path_parts else "unknown_artist"


def extract_csrf_token(soup: BeautifulSoup) -> Optional[str]:
    """
    Extracts the CSRF token from the HTML content using BeautifulSoup.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object containing the HTML
            content.

    Returns:
        Optional[str]: The extracted CSRF token, or None if not found.
    """
    script_tags: ResultSet[Any] = soup.find_all("script")

    # Look for the script that contains the CSRF token
    for tag in script_tags:
        if tag.string and "window.__CSRF_TOKEN__" in tag.string:
            match: re.Match[str] | None = re.search(
                r"window\.__CSRF_TOKEN__\s=\s'([^\"]+)'", tag.string
            )
            if match:
                return match.group(1)

    return None


def save_image(content: bytes, url: str, download_path: Path) -> Path:
    """
    Saves the image content to a file in the specified download path. The file
    name is derived from the URL.

    Args:
        content (bytes): The image content to save.
        url (str): The URL of the image.
        download_path (Path): The path to save the image.

    Returns:
        Path: The path to the saved image file.
    """
    image_name: str = Path(urlparse(url).path).name
    image_path: Path = (download_path / image_name).resolve()
    with open(image_path, "wb") as file:
        file.write(content)
    print(f"Image saved to {image_path}")

    return image_path


def ensure_path_exists(folder_name: str) -> Path:
    # Create directory for the artist if it doesn't exist
    artist_path: Path = (DOWNLOAD_PATH / folder_name).resolve()
    artist_path.mkdir(parents=True, exist_ok=True)
    return artist_path


def save_deviantart_art(
    session: Session,
    url: str,
    headers: dict[str, str],
    artist: Optional[str] = None,
) -> None:
    """
    Extracts the image URL from the HTML content and saves the image to a file.
    If the session cookies change, it retries the request with updated cookies.

    Args:
        session (requests.Session): The requests session to use.
        url (str): The URL to send the request to.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist for saving the image. If not
            provided, it will be extracted from the URL.
    """
    response: Response | None = send_request(session=session, url=url, headers=headers)
    if not response:
        return

    if not artist:
        print("No artist name provided.")
        artist = extract_artist_name(url)

    # Create directory for the artist if it doesn't exist
    artist_path: Path = ensure_path_exists(artist)

    img_classes: list[str] = ["TZM0T", "_2NIJr"]
    img_url: str | None = extract_image_url(response.text, img_classes)
    if not img_url:
        return

    response = get(img_url)
    if not response.ok:
        print_response_summary(response)
        return

    save_image(response.content, img_url, artist_path)


def get_gallery_media(
    session: Session, url: str, headers: dict[str, str], artist: str
) -> list[str]:
    """
    Retrieves the gallery media from the specified URL using the provided
    session and headers. It extracts the total number of images and constructs
    the API URL for fetching the media.

    Args:
        session (requests.Session): The requests session to use.
        url (str): The URL to send the request to.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist.

    Returns:
        list[str]: A list of URLs for the gallery media.
    """
    response: Response | None = send_request(session=session, url=url, headers=headers)
    if not response:
        return []

    soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
    span_tag: Tag | NavigableString | None = soup.find("span", class_="_1Mrww")
    if span_tag is None or isinstance(span_tag, NavigableString):
        print("Span tag not found.")
        return []

    total_images: int = int(span_tag.text.strip())
    print(f"Total images: {total_images}")

    csrf_token: str | None = extract_csrf_token(soup)
    if not csrf_token:
        print("CSRF token not found.")
        return []

    folder_id: str = urlparse(url).path.split("/gallery/")[1].split("/")[0]
    params: dict[str, str | int] = {
        "username": artist,
        "type": "gallery",
        "order": "default",
        "offset": 0,
        "limit": MAX_GALLERY_ITEMS,
        "folderid": folder_id,
        "da_minor_version": 20230710,
        "csrf_token": csrf_token,
    }

    api_url = "https://deviantart.com/_puppy/dashared/gallection/contents"
    response = send_request(
        session=session, url=api_url, headers=headers, params=params
    )
    if not response:
        print("Failed to retrieve gallery media.")
        return []

    results = response.json().get("results", [])
    print(f"Number of results: {len(results)}")
    input("Press Enter to continue...")

    return results


def save_deviantart_gallery(
    session: Session,
    url: str,
    headers: dict[str, str],
    artist: Optional[str] = None,
) -> None:
    """
    Extracts the gallery media from the specified URL and saves each image to
    a file. If the session cookies change, it retries the request with updated
    cookies.

    Args:
        session (requests.Session): The requests session to use.
        url (str): The URL to send the request to.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist. If not provided, it will be
            extracted from the URL.
    """
    if not artist:
        print("No artist name provided.")
        artist = extract_artist_name(url)

    for url in get_gallery_media(
        session=session, url=url, headers=headers, artist=artist
    ):
        # Extract and save the image
        print(f"Extracting and saving image from {url}...")
        save_deviantart_art(session, url, headers, artist)
