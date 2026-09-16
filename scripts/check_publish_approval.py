from __future__ import annotations

import argparse
import os

import requests

from common import DATA_DIR, load_environment, require_env, save_json


def get_issue(owner: str, repo: str, issue_number: int, token: str) -> dict:
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_comments(owner: str, repo: str, issue_number: int, token: str) -> list[dict]:
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether a GitHub issue approves publishing a video.")
    parser.add_argument("--issue-number", required=True, type=int)
    args = parser.parse_args()

    load_environment()
    repository = require_env("GITHUB_REPOSITORY")
    owner, repo = repository.split("/", 1)
    token = require_env("GITHUB_TOKEN")
    issue = get_issue(owner, repo, args.issue_number, token)
    comments = get_comments(owner, repo, args.issue_number, token)
    labels = {label["name"] for label in issue.get("labels", [])}
    approved = "publish-approved" in labels
    payload = {
        "issue_number": args.issue_number,
        "approved": approved,
        "labels": sorted(labels),
        "comments_checked": len(comments),
        "issue_title": issue.get("title"),
    }
    save_json(DATA_DIR / "publish_approval.json", payload)
    print(payload)


if __name__ == "__main__":
    main()
