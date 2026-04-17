// go-scanner/main.go
// Lightweight HTTP microservice that checks repo dependencies for known CVEs.
// Runs independently on port 8080 — Node.js API calls it via HTTP.

package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"
)

// ── Data models ───────────────────────────────────────────────────────────────

type Vulnerability struct {
	Package     string `json:"package"`
	CVEID       string `json:"cve_id"`
	Severity    string `json:"severity"`
	Description string `json:"description"`
}

type ScanResult struct {
	Owner           string          `json:"owner"`
	Repo            string          `json:"repo"`
	Vulnerabilities []Vulnerability `json:"vulnerabilities"`
	ScannedAt       string          `json:"scanned_at"`
	TotalChecked    int             `json:"total_checked"`
}

type GitHubContent struct {
	Content  string `json:"content"`
	Encoding string `json:"encoding"`
}

// ── Known vulnerable packages (demo dataset) ─────────────────────────────────
// In production this would query the OSV API (https://osv.dev) or NVD.
var knownVulnerable = map[string]Vulnerability{
	"requests==2.19.0": {
		CVEID:       "CVE-2018-18074",
		Severity:    "HIGH",
		Description: "requests sends HTTP Authorization header to the redirect destination",
	},
	"django==2.2.0": {
		CVEID:       "CVE-2019-14232",
		Severity:    "MEDIUM",
		Description: "Potential denial-of-service via certain regex patterns",
	},
	"flask==0.12.0": {
		CVEID:       "CVE-2018-1000656",
		Severity:    "HIGH",
		Description: "Flask is vulnerable to Denial of Service via crafted JSON",
	},
	"lodash==4.17.10": {
		CVEID:       "CVE-2019-10744",
		Severity:    "CRITICAL",
		Description: "Prototype pollution attack via defaultsDeep",
	},
	"express==4.16.0": {
		CVEID:       "CVE-2022-24999",
		Severity:    "MEDIUM",
		Description: "qs prototype poisoning vulnerability",
	},
}

// ── GitHub API helpers ────────────────────────────────────────────────────────

func fetchFileFromGitHub(owner, repo, filename string) (string, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/contents/%s", owner, repo, filename)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", fmt.Errorf("file not found: %s", filename)
	}

	body, _ := io.ReadAll(resp.Body)
	var content GitHubContent
	if err := json.Unmarshal(body, &content); err != nil {
		return "", err
	}

	if content.Encoding == "base64" {
		cleaned := strings.ReplaceAll(content.Content, "\n", "")
		decoded, err := base64.StdEncoding.DecodeString(cleaned)
		if err != nil {
			return "", err
		}
		return string(decoded), nil
	}
	return content.Content, nil
}

// ── CVE scanning logic ────────────────────────────────────────────────────────

func scanDependencies(owner, repo string) ScanResult {
	result := ScanResult{
		Owner:           owner,
		Repo:            repo,
		Vulnerabilities: []Vulnerability{},
		ScannedAt:       time.Now().UTC().Format(time.RFC3339),
	}

	// Try common dependency files
	depFiles := []string{"requirements.txt", "package.json", "Pipfile"}
	var allDeps []string

	for _, f := range depFiles {
		content, err := fetchFileFromGitHub(owner, repo, f)
		if err != nil {
			continue
		}
		deps := parseDependencies(f, content)
		allDeps = append(allDeps, deps...)
	}

	result.TotalChecked = len(allDeps)

	// Check each dependency against known vulnerable versions
	for _, dep := range allDeps {
		dep = strings.TrimSpace(strings.ToLower(dep))
		if vuln, found := knownVulnerable[dep]; found {
			vuln.Package = dep
			result.Vulnerabilities = append(result.Vulnerabilities, vuln)
		}
	}

	return result
}

func parseDependencies(filename, content string) []string {
	var deps []string
	lines := strings.Split(content, "\n")

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "//") {
			continue
		}
		// requirements.txt: requests==2.31.0 or requests>=2.0
		if filename == "requirements.txt" {
			deps = append(deps, strings.ToLower(line))
		}
		// package.json: just collect the raw line for demo
		if filename == "package.json" && strings.Contains(line, ":") {
			parts := strings.Split(line, ":")
			if len(parts) == 2 {
				pkg := strings.Trim(parts[0], `" `)
				ver := strings.Trim(parts[1], `" ,^~`)
				if pkg != "" && ver != "" && !strings.HasPrefix(pkg, "_") {
					deps = append(deps, fmt.Sprintf("%s==%s", pkg, ver))
				}
			}
		}
	}

	return deps
}

// ── HTTP handlers ─────────────────────────────────────────────────────────────

func scanHandler(w http.ResponseWriter, r *http.Request) {
	owner := r.URL.Query().Get("owner")
	repo  := r.URL.Query().Get("repo")

	if owner == "" || repo == "" {
		http.Error(w, `{"error":"owner and repo required"}`, http.StatusBadRequest)
		return
	}

	result := scanDependencies(owner, repo)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"status":"ok","service":"cve-scanner"}`)
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	http.HandleFunc("/scan",   scanHandler)
	http.HandleFunc("/health", healthHandler)

	log.Println("CVE scanner running on http://localhost:8080")
	log.Println("Usage: GET /scan?owner=facebook&repo=react")
	log.Fatal(http.ListenAndServe(":8080", nil))
}
