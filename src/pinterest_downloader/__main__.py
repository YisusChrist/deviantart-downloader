from urllib.parse import ParseResult, urlparse

from requests import Session
from rich import print

from pinterest_downloader.cookies import load_cookies, save_cookies
from pinterest_downloader.scrape import save_deviantart_art


def is_valid_deviantart_url(url: str) -> tuple[bool, str]:
    parsed: ParseResult = urlparse(url)
    if not parsed.netloc.endswith("deviantart.com"):
        return False, ""

    parts: list[str] = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return False, ""

    return parts[1] in {"art", "gallery"}, parts[1]


def main() -> None:
    url: str | None = input("Enter URL: ")
    if not url:
        print("No URL provided.")
        return

    session = Session()

    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    }
    cookies: dict[str, str] = load_cookies()
    if not cookies:
        print("No cookies found. Please log in first.")
        return

    session.cookies.update(cookies)  # type: ignore

    parsed_url: ParseResult = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print("Invalid URL provided.")
        return

    # Check if the URL is a valid Deviantart URL
    valid, path_type = is_valid_deviantart_url(url)
    if not valid:
        print("Invalid Deviantart URL provided.")
        return

    # Check if the URL is a gallery or art URL
    if path_type == "gallery":
        print("Gallery URL provided.")
        save_deviantart_art(session, url, headers)
    elif path_type == "deviation":
        print("Deviation URL provided.")
        save_deviantart_art(session, url, headers)
    elif path_type == "art":
        print("Art URL provided.")
        save_deviantart_art(session, url, headers)
    else:
        print("Unknown URL type provided.")

    # Save cookies to file
    save_cookies(session.cookies.get_dict())


if __name__ == "__main__":
    main()
