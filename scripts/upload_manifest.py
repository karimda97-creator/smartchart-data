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

api_headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# پیدا کردن Release بر اساس Tag
release_url = (
    f"https://api.github.com/repos/"
    f"{REPO}/releases/tags/{TAG_NAME}"
)

print(f"Finding release: {TAG_NAME}")

response = requests.get(
    release_url,
    headers=api_headers,
    timeout=60,
)

if response.status_code != 200:
    print("GitHub API response:")
    print(response.status_code)
    print(response.text)

    raise RuntimeError(
        "Failed to find GitHub Release"
    )

release = response.json()

upload_url = release.get("upload_url")

if not upload_url:
    raise RuntimeError(
        "Release upload_url was not found"
    )

# حذف بخش template از upload_url
upload_url = upload_url.split("{")[0]

print(f"Upload URL: {upload_url}")

# اگر guide.json قبلاً در Release وجود داشته باشد،
# ابتدا آن را پیدا و حذف می‌کنیم.
assets = release.get("assets", [])

for asset in assets:

    if asset.get("name") == "guide.json":

        asset_id = asset.get("id")

        delete_url = (
            f"https://api.github.com/repos/"
            f"{REPO}/releases/assets/{asset_id}"
        )

        print("Existing guide.json found. Deleting old asset...")

        delete_response = requests.delete(
            delete_url,
            headers=api_headers,
            timeout=60,
        )

        if delete_response.status_code not in (204, 200):

            print("Delete response:")
            print(delete_response.status_code)
            print(delete_response.text)

            raise RuntimeError(
                "Failed to delete existing guide.json"
            )

# آپلود guide.json جدید
upload_headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28",
}

print("Uploading guide.json...")

with open(MANIFEST_FILE, "rb") as file:

    upload_response = requests.post(
        upload_url,
        headers=upload_headers,
        params={
            "name": "guide.json"
        },
        data=file,
        timeout=60,
    )

if upload_response.status_code not in (200, 201):

    print("GitHub upload response:")
    print(upload_response.status_code)
    print(upload_response.text)

    raise RuntimeError(
        "Failed to upload guide.json to GitHub Release"
    )

print("guide.json uploaded successfully.")

if name == "main":

try:
    upload_manifest()

except Exception as error:

    print(f"ERROR: {error}")
    sys.exit(1)
:

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
