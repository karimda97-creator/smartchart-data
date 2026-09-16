import os
import sys
import requests


REPO = os.environ.get("REPO", "")
TAG_NAME = os.environ.get("TAG_NAME", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

MANIFEST_FILE = "manifest.json"
MANIFEST_ASSET_NAME = "manifest.json"


def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def validate_environment():

    if not REPO:
        raise ValueError(
            "REPO environment variable is missing"
        )

    if not TAG_NAME:
        raise ValueError(
            "TAG_NAME environment variable is missing"
        )

    if not GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN environment variable is missing"
        )

    if not os.path.isfile(MANIFEST_FILE):
        raise FileNotFoundError(
            f"{MANIFEST_FILE} was not generated"
        )


def get_release():

    url = (
        f"https://api.github.com/repos/"
        f"{REPO}/releases/tags/{TAG_NAME}"
    )

    response = requests.get(
        url,
        headers=get_headers(),
        timeout=60
    )

    if response.status_code != 200:

        print(
            "GitHub API response:",
            response.status_code
        )

        print(response.text)

        raise RuntimeError(
            "Failed to find GitHub Release"
        )

    return response.json()


def delete_old_manifest(release):

    assets = release.get("assets", [])

    for asset in assets:

        if asset.get("name") != MANIFEST_ASSET_NAME:
            continue

        asset_id = asset.get("id")

        if not asset_id:
            continue

        delete_url = (
            f"https://api.github.com/repos/"
            f"{REPO}/releases/assets/{asset_id}"
        )

        print(
            f"Deleting old {MANIFEST_ASSET_NAME}..."
        )

        response = requests.delete(
            delete_url,
            headers=get_headers(),
            timeout=60
        )

        if response.status_code not in (200, 204):

            print(
                "Delete response:",
                response.status_code
            )

            print(response.text)

            raise RuntimeError(
                "Failed to delete old manifest.json"
            )

        print("Old manifest deleted.")

        return


    print(
        "No previous manifest.json found."
    )


def upload_manifest(release):

    upload_url = release.get("upload_url")

    if not upload_url:
        raise RuntimeError(
            "Release upload_url was not found"
        )

    # GitHub returns something like:
    #
    # https://uploads.github.com/repos/OWNER/REPO/releases/ID/assets{?name,label}
    #
    # We only need the URL before {?name,label}.

    upload_url = upload_url.split("{")[0]

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    print(
        f"Uploading {MANIFEST_ASSET_NAME}..."
    )

    with open(
        MANIFEST_FILE,
        "rb"
    ) as file:

        response = requests.post(
            upload_url,
            headers=headers,
            params={
                "name": MANIFEST_ASSET_NAME
            },
            data=file,
            timeout=60
        )

    if response.status_code not in (200, 201):

        print(
            "Upload response:",
            response.status_code
        )

        print(response.text)

        raise RuntimeError(
            "Failed to upload manifest.json"
        )

    print(
        "manifest.json uploaded successfully."
    )

    uploaded_asset = response.json()

    print(
        "Asset ID:",
        uploaded_asset.get("id")
    )

    print(
        "Download URL:",
        uploaded_asset.get("browser_download_url")
    )


def main():

    print("======================================")
    print("Uploading manifest.json")
    print("======================================")

    validate_environment()

    print(f"Repository: {REPO}")
    print(f"Release tag: {TAG_NAME}")

    release = get_release()

    print(
        f"Release found: "
        f"{release.get('name') or TAG_NAME}"
    )

    delete_old_manifest(release)

    upload_manifest(release)

    print("======================================")
    print("Done.")
    print("======================================")


if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print(
            f"ERROR: {error}",
            file=sys.stderr
        )
