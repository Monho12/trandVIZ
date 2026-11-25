"""
forecast-log-ийн мэдэгдэл (ADR 0016, #46): GitHub issue нээнэ, ижил гарчигтай нээлттэй issue байвал **давхардуулахгүй**,
түүн дээр comment нэмнэ. Зөвхөн стандарт сан: workflow-ийн хамаарал суугаагүй (pip бүтэлгүйтсэн) үед ч ажиллана.

    python3 -m src.gh_issue --title "forecast-log: workflow бүтэлгүйтлээ" --body "..."      (эсвэл --body-file f.md)

Орчин: GITHUB_TOKEN (issues: write), GITHUB_REPOSITORY (owner/name), GITHUB_API_URL (анхдагч https://api.github.com).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

PER_PAGE = 100


def open_or_comment(api, repo: str, title: str, body: str) -> tuple[str, int]:
    """api(method, path, data) -> JSON. Нээлттэй issue-уудаас (PR-ийг алгасна) яг ижил гарчигтайг хайна.
    Байвал comment ("commented", дугаар), үгүй бол шинэ issue ("opened", дугаар)."""
    page = 1
    while True:
        items = api("GET", f"repos/{repo}/issues?state=open&per_page={PER_PAGE}&page={page}")
        for it in items:
            if it.get("title") == title and "pull_request" not in it:
                api("POST", f"repos/{repo}/issues/{it['number']}/comments", {"body": body})
                return "commented", it["number"]
        if len(items) < PER_PAGE:
            break
        page += 1
    return "opened", api("POST", f"repos/{repo}/issues", {"title": title, "body": body})["number"]


def rest_api(token: str, base: str = "https://api.github.com"):
    def call(method: str, path: str, data=None):
        req = urllib.request.Request(f"{base.rstrip('/')}/{path}", method=method,
                                     data=None if data is None else json.dumps(data).encode("utf-8"),
                                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
                                              "User-Agent": "trandVIZ-forecast-log"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    return call


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--title", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file", type=Path)
    a = p.parse_args(argv)
    body = a.body if a.body is not None else a.body_file.read_text(encoding="utf-8")
    api = rest_api(os.environ["GITHUB_TOKEN"], os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    what, number = open_or_comment(api, os.environ["GITHUB_REPOSITORY"], a.title, body)
    print(f"issue #{number}: {what}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
