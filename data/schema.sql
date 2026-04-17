-- data/schema.sql
-- Run this in MySQL Workbench or via: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS devhealth;
USE devhealth;

-- Core scans table
CREATE TABLE IF NOT EXISTS scans (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    owner           VARCHAR(100)    NOT NULL,
    repo            VARCHAR(100)    NOT NULL,
    health_score    INT             NOT NULL DEFAULT 0,
    total_commits   INT             DEFAULT 0,
    open_issues     INT             DEFAULT 0,
    closed_issues   INT             DEFAULT 0,
    unique_authors  INT             DEFAULT 0,
    languages       JSON,
    raw_json        JSON,
    scanned_at      DATETIME        NOT NULL,
    UNIQUE KEY uq_repo (owner, repo)
);

-- Scan history (one row per scan run — for trending over time)
CREATE TABLE IF NOT EXISTS scan_history (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    owner           VARCHAR(100)    NOT NULL,
    repo            VARCHAR(100)    NOT NULL,
    health_score    INT             NOT NULL,
    total_commits   INT             DEFAULT 0,
    open_issues     INT             DEFAULT 0,
    scanned_at      DATETIME        NOT NULL,
    INDEX idx_repo (owner, repo),
    INDEX idx_date (scanned_at)
);

-- CVE scan results from Go microservice
CREATE TABLE IF NOT EXISTS cve_results (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    owner           VARCHAR(100)    NOT NULL,
    repo            VARCHAR(100)    NOT NULL,
    package_name    VARCHAR(200)    NOT NULL,
    cve_id          VARCHAR(50),
    severity        ENUM('LOW','MEDIUM','HIGH','CRITICAL') DEFAULT 'LOW',
    description     TEXT,
    scanned_at      DATETIME        NOT NULL,
    INDEX idx_repo (owner, repo)
);
