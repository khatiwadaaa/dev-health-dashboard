"""
python-processor/analyzer.py

Fetches GitHub repo data via REST API, runs MapReduce-style aggregations
using Pandas, and writes results to MySQL for the Node.js API to serve.
"""

import requests
import pandas as pd
import mysql.connector
import json
import sys
from datetime import datetime
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_API   = "https://api.github.com"
GITHUB_TOKEN = ""          # optional — paste your GitHub token here for higher rate limits
DB_CONFIG    = {
    "host":     "localhost",
    "user":     "root",
    "password": "Monsoon@123",   # ← change this
    "database": "devhealth"
}

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# ── GitHub API helpers ────────────────────────────────────────────────────────

def fetch_repo_info(owner: str, repo: str) -> dict:
    """Fetch basic repo metadata from GitHub API."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()


def fetch_commits(owner: str, repo: str, max_pages: int = 5) -> list[dict]:
    """Fetch recent commits (paginated). Returns flat list of commit dicts."""
    commits = []
    for page in range(1, max_pages + 1):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
        r = requests.get(url, headers=HEADERS, params={"per_page": 100, "page": page})
        if r.status_code != 200 or not r.json():
            break
        commits.extend(r.json())
    return commits


def fetch_issues(owner: str, repo: str) -> list[dict]:
    """Fetch open and closed issues."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
    r = requests.get(url, headers=HEADERS, params={"state": "all", "per_page": 100})
    r.raise_for_status()
    return r.json()


def fetch_languages(owner: str, repo: str) -> dict:
    """Fetch language breakdown (bytes per language)."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/languages"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

# ── MapReduce-style analysis ──────────────────────────────────────────────────

def analyze_commits(commits: list[dict]) -> dict:
    """
    MapReduce pattern:
      MAP   — extract (author, date, additions, deletions) from each commit
      REDUCE — group by author → count commits, sum changes
    """
    if not commits:
        return {}

    # MAP phase — extract relevant fields into flat records
    records = []
    for c in commits:
        commit_data = c.get("commit", {})
        author      = commit_data.get("author", {})
        records.append({
            "author":  (c.get("author") or {}).get("login", author.get("name", "unknown")),
            "date":    author.get("date", ""),
            "message": commit_data.get("message", "")[:80],
        })

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df["week"]  = df["date"].dt.to_period("W").astype(str)

    # REDUCE phase — aggregate by author
    by_author = (
        df.groupby("author")
          .agg(commit_count=("author", "count"))
          .reset_index()
          .sort_values("commit_count", ascending=False)
    )

    # REDUCE phase — aggregate by week (commit frequency trend)
    by_week = (
        df.groupby("week")
          .agg(commits=("author", "count"))
          .reset_index()
          .sort_values("week")
    )

    return {
        "total_commits":  len(df),
        "unique_authors": df["author"].nunique(),
        "top_authors":    by_author.head(5).to_dict(orient="records"),
        "weekly_trend":   by_week.tail(12).to_dict(orient="records"),
    }


def analyze_issues(issues: list[dict]) -> dict:
    """Segment issues by state and compute average close time."""
    if not issues:
        return {}

    df = pd.DataFrame(issues)
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df["closed_at"]  = pd.to_datetime(df.get("closed_at"), utc=True, errors="coerce")

    open_count   = (df["state"] == "open").sum()
    closed_count = (df["state"] == "closed").sum()

    # Average time to close (hours)
    closed = df[df["state"] == "closed"].copy()
    if not closed.empty:
        closed["close_hours"] = (
            (closed["closed_at"] - closed["created_at"])
            .dt.total_seconds() / 3600
        )
        avg_close_hours = round(closed["close_hours"].mean(), 1)
    else:
        avg_close_hours = None

    # Issue labels frequency — value_counts style aggregation
    label_counts: dict = defaultdict(int)
    for _, row in df.iterrows():
        for label in row.get("labels", []):
            label_counts[label["name"]] += 1

    top_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "open_issues":      int(open_count),
        "closed_issues":    int(closed_count),
        "avg_close_hours":  avg_close_hours,
        "top_labels":       [{"label": l, "count": c} for l, c in top_labels],
    }


def compute_health_score(repo_info: dict, commit_analysis: dict, issue_analysis: dict) -> int:
    """
    Weighted health score (0–100):
      - Recent activity (commits last 4 weeks) : 30 pts
      - Issue resolution rate                  : 30 pts
      - Stars / community signal               : 20 pts
      - Has description + topics               : 20 pts
    """
    score = 0

    # Activity
    total = commit_analysis.get("total_commits", 0)
    score += min(30, int(total / 10 * 30))

    # Issue resolution
    opened  = issue_analysis.get("open_issues", 0) + issue_analysis.get("closed_issues", 0)
    closed  = issue_analysis.get("closed_issues", 0)
    if opened > 0:
        score += int((closed / opened) * 30)
    else:
        score += 15  # no issues = neutral

    # Community
    stars = repo_info.get("stargazers_count", 0)
    score += min(20, int(stars / 50 * 20))

    # Metadata completeness
    if repo_info.get("description"):
        score += 10
    if repo_info.get("topics"):
        score += 10

    return min(score, 100)

# ── MySQL persistence ─────────────────────────────────────────────────────────

def save_to_db(owner: str, repo: str, result: dict):
    """
    Persist scan results to MySQL.
    Schema: devhealth.scans (see data/schema.sql)
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    cur  = conn.cursor()

    cur.execute("""
        INSERT INTO scans
            (owner, repo, health_score, total_commits, open_issues,
             closed_issues, unique_authors, languages, raw_json, scanned_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            health_score    = VALUES(health_score),
            total_commits   = VALUES(total_commits),
            open_issues     = VALUES(open_issues),
            closed_issues   = VALUES(closed_issues),
            unique_authors  = VALUES(unique_authors),
            languages       = VALUES(languages),
            raw_json        = VALUES(raw_json),
            scanned_at      = VALUES(scanned_at)
    """, (
        owner,
        repo,
        result["health_score"],
        result["commits"]["total_commits"],
        result["issues"]["open_issues"],
        result["issues"]["closed_issues"],
        result["commits"]["unique_authors"],
        json.dumps(result["languages"]),
        json.dumps(result),
        datetime.utcnow()
    ))

    conn.commit()
    cur.close()
    conn.close()
    import sys
    print(f"Analyzing {owner}/{repo}...", file=sys.stderr)

# ── Main ──────────────────────────────────────────────────────────────────────

def analyze_repo(owner: str, repo: str, save: bool = True) -> dict:
    print(f"Analyzing {owner}/{repo}...", file=sys.stderr)

    repo_info  = fetch_repo_info(owner, repo)
    commits    = fetch_commits(owner, repo)
    issues     = fetch_issues(owner, repo)
    languages  = fetch_languages(owner, repo)

    commit_analysis = analyze_commits(commits)
    issue_analysis  = analyze_issues(issues)
    health_score    = compute_health_score(repo_info, commit_analysis, issue_analysis)

    result = {
        "owner":        owner,
        "repo":         repo,
        "health_score": health_score,
        "stars":        repo_info.get("stargazers_count", 0),
        "forks":        repo_info.get("forks_count", 0),
        "description":  repo_info.get("description", ""),
        "languages":    languages,
        "commits":      commit_analysis,
        "issues":       issue_analysis,
        "scanned_at":   datetime.utcnow().isoformat(),
    }

    if save:
        save_to_db(owner, repo, result)

    return result


if __name__ == "__main__":
    owner = sys.argv[1] if len(sys.argv) > 1 else "khatiwadaaa"
    repo  = sys.argv[2] if len(sys.argv) > 2 else "cf-stats"
    result = analyze_repo(owner, repo, save=False)
    print(json.dumps(result, indent=2))
