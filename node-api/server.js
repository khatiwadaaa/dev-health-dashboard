/**
 * node-api/server.js
 * REST API — bridges the AngularJS frontend to MySQL data + Python analyzer + Go CVE scanner
 */

require("dotenv").config();
const express = require("express");
const mysql   = require("mysql2/promise");
const cors    = require("cors");
const axios   = require("axios");
const { exec } = require("child_process");
const path    = require("path");

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, "../frontend")));

// ── MySQL connection pool ─────────────────────────────────────────────────────
const pool = mysql.createPool({
    host:     process.env.DB_HOST     || "localhost",
    user:     process.env.DB_USER     || "root",
    password: process.env.DB_PASSWORD || "Monsoon@123",
    database: process.env.DB_NAME     || "devhealth",
    waitForConnections: true,
    connectionLimit:    10,
});

// ── Routes ────────────────────────────────────────────────────────────────────

/**
 * GET /api/health
 * Simple uptime check — SRE-style health endpoint
 */
app.get("/api/health", (req, res) => {
    res.json({ status: "ok", uptime: process.uptime(), timestamp: new Date() });
});

/**
 * GET /api/scans
 * Returns all previously scanned repos from MySQL
 */
app.get("/api/scans", async (req, res) => {
    try {
        const [rows] = await pool.query(
            `SELECT owner, repo, health_score, total_commits,
                    open_issues, closed_issues, unique_authors, scanned_at
             FROM scans
             ORDER BY scanned_at DESC`
        );
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

/**
 * GET /api/scans/:owner/:repo
 * Returns full scan result for a specific repo
 */
app.get("/api/scans/:owner/:repo", async (req, res) => {
    const { owner, repo } = req.params;
    try {
        const [rows] = await pool.query(
            "SELECT * FROM scans WHERE owner = ? AND repo = ?",
            [owner, repo]
        );
        if (rows.length === 0) return res.status(404).json({ error: "Not found" });
        const row = rows[0];
        row.raw_json  = JSON.parse(row.raw_json  || "{}");
        row.languages = JSON.parse(row.languages || "{}");
        res.json(row);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

/**
 * POST /api/analyze
 * Body: { owner, repo }
 * Triggers the Python analyzer as a child process, saves to MySQL, returns result
 */
app.post("/api/analyze", (req, res) => {
    const { owner, repo } = req.body;
    if (!owner || !repo) return res.status(400).json({ error: "owner and repo required" });

    const scriptPath = path.join(__dirname, "../python-processor/analyzer.py");
    const cmd = `python "${scriptPath}" ${owner} ${repo}`;

    exec(cmd, { timeout: 60000 }, (err, stdout, stderr) => {
        console.log("STDOUT:", stdout);
        console.log("STDERR:", stderr);
        console.log("ERR:", err);
        if (err && !stdout) {
            return res.status(500).json({ error: "Analysis failed", detail: stderr });
        }
        try {
            const result = JSON.parse(stdout);
            res.json(result);
        } catch(e) {
            console.log("PARSE ERROR:", e);
            res.status(500).json({ error: "Parse failed", raw: stdout });
        }
    });
});
/**
 * GET /api/cve/:owner/:repo
 * Fetches CVE scan results from Go microservice (port 8080)
 */
app.get("/api/cve/:owner/:repo", async (req, res) => {
    const { owner, repo } = req.params;
    try {
        const goRes = await axios.get(
            `http://localhost:8080/scan?owner=${owner}&repo=${repo}`,
            { timeout: 10000 }
        );
        res.json(goRes.data);
    } catch (err) {
        // Go service may not be running — return empty gracefully
        res.json({ vulnerabilities: [], note: "CVE scanner unavailable" });
    }
});

/**
 * GET /api/history/:owner/:repo
 * Returns health score trend over time from scan_history table
 */
app.get("/api/history/:owner/:repo", async (req, res) => {
    const { owner, repo } = req.params;
    try {
        const [rows] = await pool.query(
            `SELECT health_score, total_commits, open_issues, scanned_at
             FROM scan_history
             WHERE owner = ? AND repo = ?
             ORDER BY scanned_at ASC
             LIMIT 30`,
            [owner, repo]
        );
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ── Start ─────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
    console.log(`Dev Health API running on http://localhost:${PORT}`);
    console.log(`Health check: http://localhost:${PORT}/api/health`);
});
