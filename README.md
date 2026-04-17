# Dev Health Dashboard

A full-stack web application that analyzes the health of any public GitHub repository — surfacing commit trends, contributor activity, issue resolution rates, language breakdown, and dependency security vulnerabilities in a clean, real-time dashboard.

---

## Demo

> Enter any public GitHub repo (e.g. `facebook / react`) and get a full health report in seconds.

![Dashboard Preview](https://raw.githubusercontent.com/khatiwadaaa/dev-health-dashboard/main/frontend/dashboard-preview.png)

---

## Features

- **Health Score (0–100)** — weighted algorithm combining commit activity, issue resolution rate, community signals, and metadata completeness
- **Commit Analysis** — total commits, unique contributors, top authors, 12-week activity trend chart
- **Issue Tracking** — open vs closed issues, average time to close, top label breakdown
- **Language Breakdown** — doughnut chart showing language distribution by bytes of code
- **Security Scan** — Go microservice checks `requirements.txt` and `package.json` against known CVE database, flags vulnerable packages by severity (LOW / MEDIUM / HIGH / CRITICAL)
- **Persistent History** — all scans saved to MySQL; previously scanned repos load instantly from cache
- **SRE Health Endpoint** — `/api/health` returns server uptime and timestamp for monitoring

---

## Architecture

```
Browser (AngularJS + HTML5)
        │
        │  HTTP REST
        ▼
Node.js API (Express) — port 3000
        │
        ├── POST /api/analyze ──► Python processor (child process)
        │                              │
        │                              ├── GitHub REST API (commits, issues, languages)
        │                              ├── MapReduce-style Pandas aggregations
        │                              └── Writes results to MySQL
        │
        ├── GET /api/cve ────────► Go microservice — port 8080
        │                              │
        │                              └── Fetches dependency files from GitHub
        │                                  Checks against CVE dataset
        │
        └── GET /api/scans ──────► MySQL (cached results)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | AngularJS, HTML5, CSS3, Chart.js |
| API Server | Node.js, Express.js, REST |
| Data Processing | Python, Pandas, NumPy, GitHub REST API |
| Security Scanner | Go (Golang) microservice |
| Database | MySQL — normalized schema with 3 tables |
| Data Patterns | MapReduce-style aggregation, data modeling, data validation |
| Platform | UNIX shell, Git |

---

## Project Structure

```
dev-health-dashboard/
├── python-processor/
│   ├── analyzer.py          # GitHub API fetcher + MapReduce aggregations
│   └── requirements.txt
├── node-api/
│   ├── server.js            # Express REST API — orchestrates all services
│   └── package.json
├── go-scanner/
│   └── main.go              # CVE dependency scanner microservice
├── frontend/
│   ├── index.html           # AngularJS single-page app
│   ├── app.js               # AngularJS controller + Chart.js rendering
│   └── style.css
└── data/
    └── schema.sql           # MySQL schema — scans, scan_history, cve_results
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- Go 1.21+
- MySQL 8.0+

### 1. Clone the repo
```bash
git clone https://github.com/khatiwadaaa/dev-health-dashboard.git
cd dev-health-dashboard
```

### 2. Database setup
```bash
mysql -u root -p
source data/schema.sql
```

### 3. Configure credentials
In `python-processor/analyzer.py` and `node-api/server.js`, set your MySQL password:
```python
"password": "your_mysql_password"
```

### 4. Install Python dependencies
```bash
cd python-processor
pip install -r requirements.txt
```

### 5. Install Node.js dependencies
```bash
cd node-api
npm install
```

### 6. Start all services

Open 3 terminal tabs:

**Tab 1 — API server:**
```bash
cd node-api
node server.js
```

**Tab 2 — CVE scanner:**
```bash
cd go-scanner
go run main.go
```

**Tab 3 — Open the dashboard:**
```
http://localhost:3000
```

---

## How It Works

### Python — MapReduce-style analysis
The analyzer fetches raw commit and issue data from the GitHub API, then applies MapReduce-style aggregations using Pandas:

```python
# MAP — extract fields from each commit
records = [{"author": ..., "date": ..., "message": ...} for c in commits]
df = pd.DataFrame(records)

# REDUCE — group by author, count commits
by_author = df.groupby("author").agg(commit_count=("author", "count"))

# REDUCE — group by week for trend analysis
by_week = df.groupby("week").agg(commits=("author", "count"))
```

### Go — CVE microservice
The Go service fetches `requirements.txt` or `package.json` directly from the GitHub API (base64 decoded), parses dependency versions, and checks against a CVE dataset:

```go
GET /scan?owner=facebook&repo=react
→ { "vulnerabilities": [...], "total_checked": 42 }
```

### Node.js — API orchestration
Express coordinates between the frontend, Python child process, Go microservice, and MySQL pool — clean client-server separation with REST endpoints.

### AngularJS — Frontend
Single-page app with two-way data binding. Chart.js renders the language doughnut and weekly commit trend line chart dynamically after each scan.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | SRE uptime check |
| GET | `/api/scans` | All cached scans from MySQL |
| GET | `/api/scans/:owner/:repo` | Single repo cached result |
| POST | `/api/analyze` | Trigger fresh analysis |
| GET | `/api/cve/:owner/:repo` | CVE dependency scan |
| GET | `/api/history/:owner/:repo` | Health score trend over time |

---

## Skills Demonstrated

`Python` · `Pandas` · `MapReduce` · `REST API` · `data modeling` · `data science` · `Node.js` · `Express` · `AngularJS` · `HTML5` · `CSS` · `MySQL` · `Golang` · `information security` · `SRE` · `UNIX` · `back-end` · `front-end` · `web development` · `client-server architecture` · `OOP`

---

## Author

**Monsoon Khatiwada** — [github.com/khatiwadaaa](https://github.com/khatiwadaaa)

Sophomore, B.S. Computer Science & Mathematics — Dakota State University
