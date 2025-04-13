import re
from pathlib import Path
from typing import Any, Generator, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from bs4.element import NavigableString, ResultSet, Tag
from fake_useragent import UserAgent
from requests_cache import AnyResponse, CachedSession
from requests_pprint import print_response_summary
from rich import print

from pinterest_downloader.consts import DOWNLOAD_PATH, MAX_GALLERY_ITEMS

ua = UserAgent(min_version=120.0)
_user_agent: str = ""

ok_count: int = 0
error_list: list[str] = []


def get_user_agent() -> str:
    global _user_agent

    if _user_agent == "":
        _user_agent = ua.random
    return _user_agent


def send_request(*, session: CachedSession, **kwargs: Any) -> Optional[AnyResponse]:
    """
    Sends a GET request to the specified URL with the given headers and
    session. If the response is not OK, it prints the response summary and
    exits the program.

    Args:
        session (requests_cache.CachedSession): The requests session to use.
        **kwargs: Additional keyword arguments like 'url', 'headers', etc.

    Returns:
        Optional[requests_cache.AnyResponse]: The response if successful, else
            None.
    """
    response: AnyResponse = session.get(**kwargs)
    if not response.ok:
        print_response_summary(response)
        return None

    if "Set-Cookie" in response.headers:
        # Check if the session cookie auth has been deleted
        if "auth=deleted" in response.headers["Set-Cookie"]:
            print("Session cookies have been deleted. Please log in again.")
            return None

        print("[yellow]Session cookies have changed. Sending request again...[/]")
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
    global ok_count

    image_name: str = Path(urlparse(url).path).name
    image_path: Path = (download_path / image_name).resolve()
    with open(image_path, "wb") as file:
        file.write(content)
    # print(f"Image saved to {image_path}")

    ok_count += 1

    return image_path


def ensure_path_exists(folder_name: str) -> Path:
    """
    Ensures that the directory for the artist exists. If not, it creates it.

    Args:
        folder_name (str): The name of the artist.

    Returns:
        Path: The path to the artist's directory.
    """
    # Create directory for the artist if it doesn't exist
    artist_path: Path = (DOWNLOAD_PATH / folder_name).resolve()
    artist_path.mkdir(parents=True, exist_ok=True)
    return artist_path


def download_media(session: CachedSession, url: str, artist_path: Path) -> None:
    """
    Downloads media from the specified URL and saves it to the given artist path.
    If the response is not OK, it prints the response summary.

    Args:
        url (str): The URL to download the media from.
        artist_path (Path): The path to save the downloaded media.
    """
    response: AnyResponse = session.get(url)
    if not response.ok:
        print_response_summary(response)
        return

    save_image(response.content, url, artist_path)


def save_deviantart_art(
    session: CachedSession,
    url: str,
    headers: dict[str, str],
    artist: Optional[str] = None,
) -> None:
    """
    Extracts the image URL from the HTML content and saves the image to a file.
    If the session cookies change, it retries the request with updated cookies.

    Args:
        session (requests_cache.CachedSession): The requests session to use.
        url (str): The URL to send the request to.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist for saving the image. If not
            provided, it will be extracted from the URL.
    """
    response: AnyResponse | None = send_request(
        session=session, url=url, headers=headers
    )
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

    download_media(session, img_url, artist_path)


def _extract_total_images(soup: BeautifulSoup) -> Optional[int]:
    """
    Extracts the total number of images from the HTML content using BeautifulSoup.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object containing the HTML
            content.

    Returns:
        Optional[int]: The total number of images, or None if not found.
    """
    span_tag: Tag | NavigableString | None = soup.find("span", class_="_1Mrww")
    if not span_tag or isinstance(span_tag, NavigableString):
        print("Total image count not found.")
        return None
    try:
        return int(span_tag.text.strip())
    except ValueError:
        print("Failed to parse total image count.")
        return None


def _fetch_media_batch(
    session: CachedSession,
    headers: dict[str, str],
    artist: str,
    folder_id: str,
    offset: int,
    csrf_token: str,
) -> Optional[dict[str, Any]]:
    """
    Fetches a batch of media items from the DeviantArt API.

    Args:
        session (requests_cache.CachedSession): The requests session to use.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist.
        folder_id (str): The ID of the folder.
        offset (int): The offset for pagination.
        csrf_token (str): The CSRF token for authentication.

    Returns:
        Optional[dict[str, Any]]: The response JSON containing media URLs and
            pagination information.
    """
    params: dict[str, str | int] = {
        "username": artist,
        "type": "gallery",
        "order": "default",
        "offset": offset,
        "limit": MAX_GALLERY_ITEMS,
        "folderid": folder_id,
        "da_minor_version": 20230710,
        "csrf_token": csrf_token,
    }

    api_url = "https://deviantart.com/_puppy/dashared/gallection/contents"
    response: AnyResponse | None = send_request(
        session=session, url=api_url, headers=headers, params=params
    )
    if not response:
        print("Failed to fetch gallery media batch.")
        return None

    response_json: dict[str, Any] | None = response.json()
    if not response_json:
        print("No results found.")
        return None

    results: list[dict[str, Any]] = response_json.get("results", [])
    print(f"Number of results: {len(results)}")

    return {
        "urls": _extract_image_urls_from_results(results),
        "has_more": response_json.get("hasMore", False),
        "next_offset": response_json.get("nextOffset", offset + MAX_GALLERY_ITEMS),
    }


def _extract_image_urls_from_results(results: list[dict[str, Any]]) -> list[str]:
    """
    Extracts image URLs from the results list.

    Args:
        results (list[dict[str, Any]]): The list of results containing media
            information.
    Returns:
        list[str]: A list of extracted image URLs.
    """
    media_urls: list[str] = []
    for item in results:
        # Extract URL and token from item["media"]
        media: dict[str, Any] = item.get("media", {})
        if not media:
            continue

        base_uri: str | None = media.get("baseUri")
        pretty_name: str | None = media.get("prettyName")
        token_list: list[str] | None = media.get("token", [])
        types: list[dict[str, Any]] = media.get("types", [])

        # Basic validation
        if not (base_uri and pretty_name and token_list and types):
            continue

        token: str = token_list[0]

        # Find the 'fullview' type
        fullview: dict[str, Any] | None = next(
            (t for t in types if t.get("t") == "fullview"), None
        )
        if not fullview or not fullview.get("c"):
            error_list.append(item["url"])
            continue

        # Build the full URL
        image_path: str = fullview["c"].replace("<prettyName>", pretty_name)
        media_url: str = f"{base_uri}{image_path}?token={token}"
        media_urls.append(media_url)

    return media_urls


def get_gallery_media(
    session: CachedSession, url: str, headers: dict[str, str], artist: str
) -> Generator[list[str], None, None]:
    """
    Retrieves the gallery media from the specified URL using the provided
    session and headers. It extracts the total number of images and constructs
    the API URL for fetching the media.

    Args:
        session (requests_cache.CachedSession): The requests session to use.
        url (str): The URL to send the request to.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist.

    Returns:
        Generator[list[str], None, None]: A generator yielding lists of media
            URLs.
    """
    response: AnyResponse | None = send_request(
        session=session, url=url, headers=headers
    )
    if not response:
        return

    soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
    span_tag: Tag | NavigableString | None = soup.find("span", class_="_1Mrww")
    if span_tag is None or isinstance(span_tag, NavigableString):
        print("Span tag not found.")
        return

    total_images: int | None = _extract_total_images(soup)
    if total_images is None:
        return

    print(f"Total images: {total_images}")

    csrf_token: str | None = extract_csrf_token(soup)
    if not csrf_token:
        print("CSRF token not found.")
        return

    folder_id: str = urlparse(url).path.split("/gallery/")[1].split("/")[0]
    offset: int = 0

    has_more: bool = True
    while has_more:
        media_batch: dict[str, Any] | None = _fetch_media_batch(
            session,
            headers,
            artist,
            folder_id,
            offset,
            csrf_token,
        )
        if not media_batch:
            break

        print("Found total images:", len(media_batch["urls"]))
        yield media_batch["urls"]

        if not media_batch["has_more"]:
            break
        offset = media_batch["next_offset"]


def save_deviantart_gallery(
    session: CachedSession,
    url: str,
    headers: dict[str, str],
    artist: Optional[str] = None,
) -> None:
    """
    Extracts the gallery media from the specified URL and saves each image to
    a file. If the session cookies change, it retries the request with updated
    cookies.

    Args:
        session (requests_cache.CachedSession): The requests session to use.
        url (str): The URL to send the request to.
        headers (dict[str, str]): The headers to include in the request.
        artist (str): The name of the artist. If not provided, it will be
            extracted from the URL.
    """
    if not artist:
        print("No artist name provided.")
        artist = extract_artist_name(url)

    # Create directory for the artist if it doesn't exist
    artist_path: Path = ensure_path_exists(artist)

    for batch in get_gallery_media(session, url, headers, artist):
        for media_url in batch:
            download_media(session, media_url, artist_path)

    print(ok_count)
    if error_list:
        print("Errors occurred during download:")
        for error in error_list:
            print(error)
        print(f"Total errors: {len(error_list)}")
    else:
        print("All images downloaded successfully.")
