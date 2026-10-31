#!/usr/bin/env python3
"""Keep the LIVE STATS voice channel names in The Junkyard up to date.

Renames:
    ⭐ Stars: 4.2k        total stars of all cyberjunky repos (forks not counted)
    📦 PyPI/week: 181k    weekly downloads of the packages in PACKAGES
    👥 Members: 312       server member count

Runs as a GitHub Action (see discord-stats.yml) or by hand:
    DISCORD_BOT_TOKEN=... DISCORD_GUILD_ID=... python discord_stats.py
    python discord_stats.py --dry-run     # only print the stats, no token needed

Standard library only.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

OWNER = "cyberjunky"
PACKAGES = ["garminconnect", "ha-garmin", "aiogarmin", "bitvavo-aio", "pyfireservicerota", "pymovingintelligence-ha"]
DISCORD = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/cyberjunky, 1.0) junkyard-stats"


def get_json(url, headers=None, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def short(n):
    """4210 -> 4.2k, 181234 -> 181k, 1234567 -> 1.2M"""
    for size, unit in ((1_000_000, "M"), (1_000, "k")):
        if n >= size:
            value = n / size
            text = f"{value:.1f}" if value < 10 else f"{value:.0f}"
            return text.removesuffix(".0") + unit
    return str(n)


def github_stars():
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    total, page = 0, 1
    while True:
        repos = get_json(f"https://api.github.com/users/{OWNER}/repos?type=owner&per_page=100&page={page}", headers)
        total += sum(r["stargazers_count"] for r in repos if not r["fork"])
        if len(repos) < 100:
            return total
        page += 1


def pypi_week():
    total = 0
    for pkg in PACKAGES:
        try:
            total += get_json(f"https://pypistats.org/api/packages/{pkg}/recent")["data"]["last_week"]
        except (urllib.error.URLError, KeyError) as err:
            print(f"   ! {pkg}: {err}")
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the stats, don't touch Discord")
    args = ap.parse_args()

    names = {
        "⭐ Stars": f"⭐ Stars: {short(github_stars())}",
        "📦 PyPI/week": f"📦 PyPI/week: {short(pypi_week())}",
    }

    token, gid = os.environ.get("DISCORD_BOT_TOKEN"), os.environ.get("DISCORD_GUILD_ID")
    if args.dry_run:
        print("\n".join(names.values()))
        return
    if not token or not gid:
        sys.exit("Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID (or use --dry-run).")

    auth = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    guild = get_json(f"{DISCORD}/guilds/{gid}?with_counts=true", auth)
    names["👥 Members"] = f"👥 Members: {short(guild['approximate_member_count'])}"

    channels = get_json(f"{DISCORD}/guilds/{gid}/channels", auth)
    for label, new in names.items():
        ch = next((c for c in channels if c["type"] == 2 and c["name"].split(":")[0].strip() == label), None)
        if not ch:
            print(f"   ! no voice channel starting with '{label}'")
        elif ch["name"] == new:
            print(f"   = {new}")
        else:
            # Discord allows 2 renames per channel per 10 minutes; only rename on change.
            get_json(f"{DISCORD}/channels/{ch['id']}", auth, "PATCH", {"name": new})
            print(f"   ~ {ch['name']}  ->  {new}")


if __name__ == "__main__":
    main()
