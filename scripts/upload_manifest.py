import os
import sys
import requests


REPO = os.environ.get("REPO", "")
TAG_NAME = os.environ.get("TAG_NAME", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

MANIFEST_FILE = "guide.json"


def upload_manifest():

    if not REPO:
        raise ValueError("REPO environment variable is missing")

    if not TAG_NAME:
        raise ValueError("TAG_NAME environment variable is missing")

    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable is missing")

    if not os.path.isfile(MANIFEST_FILE):
        raise FileNotFoundError(
            f"{MANIFEST_FILE} was not generated"
        )

    url = (
        f"https://uploads.github.com/repos/"
        f"{REPO}/releases/tags/{TAG_NAME}/assets"
    )

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    with open(MANIFEST_FILE, "rb") as file:

        response = requests.post(
            url,
            headers=headers,
            params={
                "name": "guide.json"
            },
            data=file,
            timeout=60,
        )

    if response.status_code not in (201, 200):

        print("GitHub API response:")
        print(response.status_code)
        print(response.text)

        raise RuntimeError(
            "Failed to upload guide.json to GitHub Release"
        )

    print("guide.json uploaded successfully.")


if __name__ == "__main__":

    try:
        upload_manifest()

    except Exception as error:

        print(f"ERROR: {error}")
        sys.exit(1)
