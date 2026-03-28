-- ============================================================
--  DEVOTEE GATHERING SYSTEM — MySQL Schema
--  Run this ONCE to set up the database
--  mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS iskcon_ramnavmi_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE iskcon_ramnavmi_db;

-- ── FAMILY REGISTRATIONS ──
-- One row = one family form submission
CREATE TABLE IF NOT EXISTS registrations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    token       VARCHAR(10)  NOT NULL UNIQUE,   -- e.g. 001, 002, 003
    name        VARCHAR(150) NOT NULL,           -- Family head name
    address     TEXT         NOT NULL,           -- Full address
    mobile      VARCHAR(15)  NOT NULL,           -- 10-digit mobile
    persons     INT          NOT NULL DEFAULT 1, -- Number of family members
    paid        INT          NOT NULL DEFAULT 0, -- Amount paid (Rs)
    reg_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_token (token),
    INDEX idx_mobile (mobile)
) ENGINE=InnoDB;

-- ── ATTENDANCE ──
-- One row = one family scanned at gate
-- persons column = all members of that family (N persons in 1 scan)
CREATE TABLE IF NOT EXISTS attendance (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    token       VARCHAR(10)  NOT NULL UNIQUE,   -- matches registrations.token
    name        VARCHAR(150) NOT NULL,
    persons     INT          NOT NULL DEFAULT 1, -- ALL family members counted here
    paid        INT          NOT NULL DEFAULT 0,
    mobile      VARCHAR(15),
    gate_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (token) REFERENCES registrations(token)
        ON DELETE CASCADE,
    INDEX idx_token (token)
) ENGINE=InnoDB;

-- ── TOKEN COUNTER ──
-- Single-row table to track the auto-increment token number
-- (Separate from MySQL AUTO_INCREMENT so token format is controllable)
CREATE TABLE IF NOT EXISTS token_counter (
    id      INT PRIMARY KEY DEFAULT 1,
    current INT NOT NULL DEFAULT 0
);

-- Seed the counter row
INSERT IGNORE INTO token_counter (id, current) VALUES (1, 0);

-- ============================================================
--  Create a dedicated user for the Flask app (recommended)
--  Replace 'yourpassword' with a strong password
-- ============================================================
-- CREATE USER IF NOT EXISTS 'iskcon_user'@'localhost'
--     IDENTIFIED BY 'yourpassword';
-- GRANT SELECT, INSERT, UPDATE, DELETE
--     ON iskcon_ramnavmi_db.*
--     TO 'iskcon_user'@'localhost';
-- FLUSH PRIVILEGES;

SELECT 'ISKCON Ram Navmi DB schema created successfully!' AS status;
