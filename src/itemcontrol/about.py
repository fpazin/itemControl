from __future__ import annotations

from . import __version__


APP_NAME = "ItemControl"
DEVELOPER_NAME = "Felipe Pazin"
DEVELOPER_URL = "https://github.com/fpazin"
REPOSITORY_URL = "https://github.com/fpazin/itemControl"
RELEASES_URL = f"{REPOSITORY_URL}/releases"


def about_details() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "version": __version__,
        "developer": DEVELOPER_NAME,
        "developer_url": DEVELOPER_URL,
        "repository_url": REPOSITORY_URL,
        "releases_url": RELEASES_URL,
    }
