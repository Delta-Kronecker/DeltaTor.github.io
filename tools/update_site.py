#!/usr/bin/env python3
"""Render index.html from index.template.html using the latest stable releases.

Reads the releases of Delta-Kronecker/Delta-Tor, picks the newest stable
release for Android (always the latest stable tag) and the newest stable tag
that actually ships a Windows x64 zip for Windows (they can differ), then
substitutes every {{TOKEN}} in the template.

The run fails instead of writing a half-updated page, so a broken run leaves
the published index.html untouched. Set GITHUB_TOKEN/GH_TOKEN to avoid the
unauthenticated rate limit.

Usage:  GH_TOKEN=<token> python3 tools/update_site.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

REPO = "Delta-Kronecker/Delta-Tor"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
TEMPLATE = "index.template.html"
OUTPUT = "index.html"
WIN_ZIP = re.compile(r"win64|windows-x64")


def fetch_releases() -> list[dict]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "deltator-site-updater",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(RELEASES_URL, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def megabytes(size: int) -> str:
    return f"{size / 1_000_000:.1f} MB"


def main() -> None:
    releases = fetch_releases()
    stable = [r for r in releases if not r["draft"] and not r["prerelease"]]
    if not stable:
        sys.exit("no stable release found")

    android = stable[0]
    android_tag = android["tag_name"]
    assets = {a["name"]: a for a in android["assets"]}

    def android_asset(variant: str) -> dict:
        name = f"deltator-{android_tag}-{variant}.apk"
        if name not in assets:
            sys.exit(f"stable release {android_tag} does not ship {name}")
        return assets[name]

    universal = android_asset("universal")
    arm64 = android_asset("arm64-v8a")
    v7a = android_asset("armeabi-v7a")

    windows, win_zip = None, None
    for release in stable:
        zips = [
            a for a in release["assets"]
            if a["name"].endswith(".zip") and WIN_ZIP.search(a["name"])
        ]
        if zips:
            windows, win_zip = release, zips[0]
            break
    if windows is None:
        sys.exit("no stable release ships a Windows x64 zip")

    tokens = {
        "AND_TAG": android_tag,
        "AND_VER": android_tag.removeprefix("v"),
        "AND_DATE": android["published_at"][:10],
        "AND_TAG_URL": android["html_url"],
        "AND_UNIVERSAL_URL": universal["browser_download_url"],
        "AND_UNIVERSAL_SIZE": megabytes(universal["size"]),
        "AND_UNIVERSAL_BYTES": str(universal["size"]),
        "AND_ARM64_URL": arm64["browser_download_url"],
        "AND_ARM64_SIZE": megabytes(arm64["size"]),
        "AND_V7A_URL": v7a["browser_download_url"],
        "AND_V7A_SIZE": megabytes(v7a["size"]),
        "WIN_TAG": windows["tag_name"],
        "WIN_VER": windows["tag_name"].removeprefix("v"),
        "WIN_DATE": windows["published_at"][:10],
        "WIN_TAG_URL": windows["html_url"],
        "WIN_URL": win_zip["browser_download_url"],
        "WIN_NAME": win_zip["name"],
        "WIN_SIZE": megabytes(win_zip["size"]),
    }

    with open(TEMPLATE, encoding="utf-8") as handle:
        html = handle.read()
    for key, value in tokens.items():
        html = html.replace("{{" + key + "}}", value)

    leftover = sorted(set(re.findall(r"\{\{(\w+)\}\}", html)))
    if leftover:
        sys.exit(f"template uses unknown placeholders: {', '.join(leftover)}")

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html)
    print(
        f"rendered {OUTPUT}: Android {android_tag}, "
        f"Windows {windows['tag_name']} ({win_zip['name']})"
    )


if __name__ == "__main__":
    main()
