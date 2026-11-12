"""Bounded GitHub REST history import for the project portal.

The importer is deliberately request-driven: it does not start a scheduler or
background loop.  Each resource type is capped so one click cannot consume
unbounded memory even for a large repository.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

import httpx


GITHUB_API = "https://api.github.com"
MAX_ITEMS_PER_TYPE = 300
MAX_BRANCHES = 20


class GithubHistoryError(RuntimeError):
    pass


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def _api_get(client: httpx.Client, path: str, params: dict | None = None):
    try:
        response = client.get(GITHUB_API + path, params=params)
    except httpx.HTTPError as exc:
        raise GithubHistoryError("无法连接 GitHub API") from exc
    if response.status_code == 404:
        raise GithubHistoryError("GitHub 仓库不存在，或私有仓库 Token 没有读取权限")
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        raise GithubHistoryError("GitHub API 请求额度已用完，请配置 Token 后重试")
    try:
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GithubHistoryError(f"GitHub API 返回异常（HTTP {response.status_code}）") from exc


def _paged(
    client: httpx.Client,
    path: str,
    params: dict,
    container: str | None = None,
    limit: int = MAX_ITEMS_PER_TYPE,
) -> list[dict]:
    result: list[dict] = []
    pages = ceil(limit / 100)
    for page in range(1, pages + 1):
        payload = _api_get(client, path, {**params, "per_page": 100, "page": page})
        items = payload.get(container, []) if container else payload
        if not isinstance(items, list):
            raise GithubHistoryError("GitHub API 返回了无法识别的数据格式")
        result.extend(item for item in items if isinstance(item, dict))
        if len(items) < 100:
            break
    return result[:limit]


def _within(value: str | None, since: datetime) -> bool:
    parsed = _parse_time(value)
    return bool(parsed and parsed >= since)


def fetch_github_history(repository: str, token: str, since: datetime) -> list[dict]:
    """Fetch recent repository history, capped at 300 items per resource type."""
    parts = repository.split("/")
    if len(parts) != 2 or not all(parts):
        raise GithubHistoryError("GitHub 仓库名必须使用 owner/repository 格式")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "LungTic-Project-Portal",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    since_iso = since.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    base = f"/repos/{repository}"
    history: list[dict] = []

    with httpx.Client(timeout=20.0, headers=headers, follow_redirects=False) as client:
        repo = _api_get(client, base)
        canonical_repository = repo.get("full_name") or repository

        branches = _paged(client, base + "/branches", {}, limit=MAX_BRANCHES)
        branch_names = [repo.get("default_branch")] + [item.get("name") for item in branches]
        branch_names = list(dict.fromkeys(name for name in branch_names if name))[:MAX_BRANCHES]
        commits_by_sha: dict[str, dict] = {}
        for branch in branch_names:
            # One page per branch is enough for bounded evidence import; SHA
            # de-duplication prevents shared ancestry from inflating activity.
            for item in _paged(client, base + "/commits", {"sha": branch, "since": since_iso}, limit=100):
                sha = item.get("sha")
                if sha and sha not in commits_by_sha:
                    commits_by_sha[sha] = item
                if len(commits_by_sha) >= MAX_ITEMS_PER_TYPE:
                    break
            if len(commits_by_sha) >= MAX_ITEMS_PER_TYPE:
                break
        commits = list(commits_by_sha.values())
        for item in commits:
            commit = item.get("commit") or {}
            author = item.get("author") or {}
            commit_author = commit.get("author") or {}
            occurred = commit_author.get("date") or (commit.get("committer") or {}).get("date")
            history.append({
                "key": f"commit:{item.get('sha')}", "event_type": "commit", "action": "committed",
                "actor_login": author.get("login") or commit_author.get("name"),
                "repository": canonical_repository,
                "title": ((commit.get("message") or "Commit").splitlines()[0])[:512],
                "url": item.get("html_url"), "reference": (item.get("sha") or "")[:7] or None,
                "occurred_at": _parse_time(occurred), "created_at": _parse_time(occurred),
                "number": None, "complete": False, "state": None, "assignee_logins": [],
            })

        pulls = _paged(client, base + "/pulls", {
            "state": "all", "sort": "updated", "direction": "desc",
        })
        for item in pulls:
            if not _within(item.get("updated_at"), since):
                continue
            merged = bool(item.get("merged_at"))
            state = item.get("state") or "open"
            action = "merged" if merged else state
            history.append({
                "key": f"pull:{item.get('id')}", "event_type": "pull_request", "action": action,
                "actor_login": (item.get("user") or {}).get("login"), "repository": canonical_repository,
                "title": str(item.get("title") or "Pull request")[:512], "url": item.get("html_url"),
                "reference": f"PR #{item.get('number')}", "occurred_at": _parse_time(item.get("updated_at")),
                "created_at": _parse_time(item.get("created_at")), "number": item.get("number"),
                "complete": merged, "state": state,
                "assignee_logins": [row.get("login") for row in item.get("assignees") or [] if row.get("login")],
            })

        issues = _paged(client, base + "/issues", {
            "state": "all", "sort": "updated", "direction": "desc", "since": since_iso,
        })
        for item in issues:
            # GitHub's issue listing also contains pull requests.
            if item.get("pull_request") or not _within(item.get("updated_at"), since):
                continue
            state = item.get("state") or "open"
            history.append({
                "key": f"issue:{item.get('id')}", "event_type": "issues", "action": state,
                "actor_login": (item.get("user") or {}).get("login"), "repository": canonical_repository,
                "title": str(item.get("title") or "Issue")[:512], "url": item.get("html_url"),
                "reference": f"Issue #{item.get('number')}", "occurred_at": _parse_time(item.get("updated_at")),
                "created_at": _parse_time(item.get("created_at")), "number": item.get("number"),
                "complete": state == "closed", "state": state,
                "assignee_logins": [row.get("login") for row in item.get("assignees") or [] if row.get("login")],
            })

        runs = _paged(client, base + "/actions/runs", {
            "created": f">={since.date().isoformat()}",
        }, "workflow_runs")
        for item in runs:
            if not _within(item.get("updated_at") or item.get("created_at"), since):
                continue
            action = item.get("conclusion") or item.get("status")
            history.append({
                "key": f"workflow:{item.get('id')}", "event_type": "workflow_run", "action": action,
                "actor_login": (item.get("actor") or {}).get("login"), "repository": canonical_repository,
                "title": str(item.get("display_title") or item.get("name") or "Workflow run")[:512],
                "url": item.get("html_url"), "reference": action,
                "occurred_at": _parse_time(item.get("updated_at") or item.get("created_at")),
                "created_at": _parse_time(item.get("created_at")), "number": None,
                "complete": False, "state": item.get("status"), "assignee_logins": [],
            })

        releases = _paged(client, base + "/releases", {})
        for item in releases:
            occurred = item.get("published_at") or item.get("created_at")
            if not _within(occurred, since):
                continue
            action = "draft" if item.get("draft") else ("prerelease" if item.get("prerelease") else "published")
            history.append({
                "key": f"release:{item.get('id')}", "event_type": "release", "action": action,
                "actor_login": (item.get("author") or {}).get("login"), "repository": canonical_repository,
                "title": str(item.get("name") or item.get("tag_name") or "Release")[:512],
                "url": item.get("html_url"), "reference": item.get("tag_name"),
                "occurred_at": _parse_time(occurred), "created_at": _parse_time(item.get("created_at")),
                "number": None, "complete": False, "state": action, "assignee_logins": [],
            })

    fallback = datetime.utcnow()
    for item in history:
        item["occurred_at"] = item.get("occurred_at") or fallback
        item["created_at"] = item.get("created_at") or item["occurred_at"]
    history.sort(key=lambda item: item["occurred_at"], reverse=True)
    return history
