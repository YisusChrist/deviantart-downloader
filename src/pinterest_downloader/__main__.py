from pathlib import Path

from requests import Session
from rich import print

from pinterest_downloader.consts import DOWNLOAD_PATH
from pinterest_downloader.cookies import load_cookies, save_cookies
from pinterest_downloader.scrape import (extract_and_save_image, extract_artist_name,
                                  get_gallery_media)


def main() -> None:
    url: str | None = input("Enter URL: ")
    if not url:
        print("No URL provided.")
        return

    session = Session()

    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    }

    cookies: dict[str, str] = load_cookies()
    if not cookies:
        print("No cookies found. Please log in first.")
        return

    session.cookies.update(cookies)  # type: ignore

    # Extract artist name from URL
    artist: str = extract_artist_name(url)
    print(f"Extracted artist name: {artist}")

    for url in get_gallery_media(
        session=session, url=url, headers=headers, artist=artist
    ):
        # Create directory for the artist if it doesn't exist
        artist_dir: Path = (DOWNLOAD_PATH / artist).resolve()
        artist_dir.mkdir(parents=True, exist_ok=True)

        # Extract and save the image
        print(f"Extracting and saving image from {url}...")
        extract_and_save_image(session, url, headers, artist_dir)

    # Save cookies to file
    save_cookies(session.cookies.get_dict())


if __name__ == "__main__":
    main()
