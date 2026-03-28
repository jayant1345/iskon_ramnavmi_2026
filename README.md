# ISKCON Society — Ram Navmi Celebration 2025
## Guest Registration & Attendance System
### MySQL + Flask + HTML | Family-wise Token & Gate Entry

---

## Overview

A local-network web application for managing family registrations and gate attendance at the ISKCON Ram Navmi event. One PC runs the server; all other devices (phones, tablets) connect via WiFi browser — no app installation needed on attendee devices.

**What it does:**
- Families self-register via a QR code link on their phone
- Each family gets a unique token QR code after registration
- Gate volunteers scan the family QR to mark attendance
- Admin dashboard shows live stats and can export a CSV report

---

## System Requirements

| Component | Requirement |
|-----------|-------------|
| Python    | 3.8 or higher |
| MySQL     | 5.7 or higher (or MariaDB 10.3+) |
| Browser   | Chrome / Edge (recommended) |
| Network   | All devices on the **same WiFi** network |
| OS        | Windows / Linux / macOS |

---

## Folder Structure

```
iskcon_ramnavmi/
├── schema.sql        ← Run once to create MySQL tables
├── app.py            ← Flask API server (backend)
├── index.html        ← Frontend UI (served from Flask)
├── requirements.txt  ← Python dependencies
└── README.md         ← This file
```

---

## Installation — Step by Step

### Step 1 — Install Python

Download Python 3.8+ from https://python.org/downloads
During installation on Windows, check **"Add Python to PATH"**.

Verify installation:
```bash
python --version
```

---

### Step 2 — Install Python Dependencies

Open a terminal/command prompt in the project folder and run:

```bash
pip install flask flask-cors pymysql
```

Or use the requirements file:

```bash
pip install -r requirements.txt
```

---

### Step 3 — Install and Start MySQL

**Windows:** Download MySQL Community Server from https://dev.mysql.com/downloads/
**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl start mysql
```

Verify MySQL is running:
```bash
# Windows — check Services app, or:
mysql -u root -p

# Linux
sudo systemctl status mysql
```

---

### Step 4 — Create the Database

Import the schema file to create all required tables:

```bash
mysql -u root -p < schema.sql
```

This creates:
- `iskcon_ramnavmi_db` — the main database
- `registrations` table — one row per registered family
- `attendance` table — one row per family scanned at gate
- `token_counter` table — tracks the auto-increment token number (001, 002, ...)

To verify it worked:
```bash
mysql -u root -p -e "SHOW TABLES FROM iskcon_ramnavmi_db;"
```

Expected output:
```
+----------------------------+
| Tables_in_iskcon_ramnavmi_db |
+----------------------------+
| attendance                 |
| registrations              |
| token_counter              |
+----------------------------+
```

---

### Step 5 — Configure Database Credentials in app.py

Open [app.py](app.py) and find the `DB_CONFIG` section near the top:

```python
DB_CONFIG = {
    'host':     'localhost',
    'port':     3306,
    'user':     'root',          # ← your MySQL username
    'password': 'yourpassword',  # ← your MySQL password
    'db':       'iskcon_ramnavmi_db',
}
```

Replace `yourpassword` (and `root` if you use a different user) with your actual MySQL credentials.

---

### Step 6 — Find Your PC's LAN IP Address

```bash
# Windows
ipconfig
# Look for: IPv4 Address . . . . : 192.168.x.xxx

# Linux / macOS
hostname -I
# or
ip addr show
```

Note this IP — example: `192.168.1.105`
All devices connecting to the system will use this IP.

---

### Step 7 — Configure the Frontend (index.html)

Open [index.html](index.html) and find these two lines near the top:

```javascript
const API = 'http://192.168.1.100:5000';   // ← CHANGE THIS to your LAN IP
const UPI_ID = 'yourname@upi';             // ← CHANGE to your UPI ID
```

Update both values:
- `API` — your PC's LAN IP from Step 6 (keep port `5000`)
- `UPI_ID` — your UPI payment ID shown to families during registration

---

### Step 8 — Start the Flask Server

In the project folder, run:

```bash
python app.py
```

You will see:

```
=======================================================
  🕉  ISKCON SOCIETY — RAM NAVMI CELEBRATION 2025
=======================================================
  Local:   http://localhost:5000
  Network: http://192.168.1.105:5000
  Health:  http://192.168.1.105:5000/api/ping
  QR URL:  http://192.168.1.105:5000/?register=1
=======================================================
  Share the Network URL with:
  • Registration device (any phone/tablet on WiFi)
  • Gate device (volunteer's phone)
  • Admin/Dashboard device (laptop)
=======================================================
```

The server is now running. Keep this terminal open throughout the event.

---

### Step 9 — Allow Port 5000 Through Windows Firewall (Windows only)

If devices on the network cannot reach the server, add a firewall rule:

1. Open **Windows Defender Firewall** → Advanced Settings
2. Click **Inbound Rules** → **New Rule**
3. Select **Port** → TCP → **5000** → Allow the connection
4. Apply to all profiles, name it `Flask-5000`

Or via command prompt (run as Administrator):
```bash
netsh advfirewall firewall add rule name="Flask Port 5000" dir=in action=allow protocol=TCP localport=5000
```

---

## How to Operate the System

### Device Roles

| Device | Who Uses It | URL to Open |
|--------|-------------|-------------|
| Admin/Server PC | Organiser | `http://localhost:5000` |
| Registration phone/tablet | Volunteer at registration desk | `http://192.168.1.105:5000` |
| Gate phone | Gate volunteer | `http://192.168.1.105:5000` |
| Dashboard screen | Admin / display board | `http://192.168.1.105:5000` |

Replace `192.168.1.105` with your actual server IP.

---

### Workflow — Step by Step

#### Before the Event

1. Start MySQL service
2. Run `python app.py` on the server PC
3. Open `http://localhost:5000` in Chrome — confirm the status pill shows **Server Online**
4. Print or display the Invite QR (shown in the Admin/Dashboard tab)
   The Invite QR URL is: `http://192.168.1.105:5000/?register=1`

---

#### During Registration (Families Arriving)

**Option A — Self-registration via QR (recommended)**
1. Family scans the **Invite QR** with their phone camera
2. Their phone opens the registration form in the browser
3. They fill in: Family Head Name, Address, Mobile, Number of Members
4. They pay via the UPI QR shown on screen
5. After submitting, they receive a **unique Family Token QR** on screen
6. They screenshot the QR or note the token number

**Option B — Staff-assisted registration**
1. Open `http://192.168.1.105:5000` on the registration desk device
2. Go to the **Registration** tab
3. Fill in the family details and submit
4. Show/print the generated QR for the family

---

#### At the Gate (Entry Scanning)

1. Open `http://192.168.1.105:5000` on the gate volunteer's phone
2. Go to the **Gate Scan** tab
3. Click **Start Camera** and point it at the family's QR code
4. On successful scan:
   - **Green banner** = Valid entry — family members counted
   - **Yellow banner** = Already entered (duplicate scan)
   - **Red banner** = Token not found (invalid QR)
5. If the camera doesn't work (HTTP on phones), use **Fill Token Manually** and type the 3-digit token number

---

#### Admin Dashboard

Open `http://192.168.1.105:5000` and go to the **Dashboard** tab to see:

- Total registered families and persons
- Total families who have arrived and persons counted
- Families still pending (registered but not yet arrived)
- Total collection amount (Rs)
- Hourly attendance chart (entries per hour)

The dashboard auto-refreshes every 5 seconds.

---

#### Exporting Data

To download a full CSV report of all registrations and attendance:

- Click **Export CSV** in the Admin tab, or
- Visit directly: `http://localhost:5000/api/export/csv`

The CSV includes: Token, Family Head, Address, Mobile, Members, Paid, Registered At, Attended (Yes/No), Members Counted, Gate Entry Time.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ping` | Health check — returns `{"status":"ok"}` |
| GET | `/api/stats` | Live summary: families, persons, collection |
| GET | `/api/registrations` | All registered families with attended flag |
| POST | `/api/register` | Register a new family |
| GET | `/api/attendance` | All gate entry records |
| GET | `/api/attendance/hourly` | Per-hour entry counts for today |
| POST | `/api/gate/scan` | Mark a family's gate entry |
| GET | `/api/export/csv` | Download full report as CSV |
| POST | `/api/admin/clear` | Wipe all data (requires secret) |

**POST /api/register — Request body:**
```json
{
  "name": "Ramesh Sharma",
  "address": "12, Vrindavan Colony, Jaipur",
  "mobile": "9876543210",
  "persons": 4,
  "paid": 200
}
```

**POST /api/gate/scan — Request body:**
```json
{
  "token": "007",
  "name": "Ramesh Sharma",
  "persons": 4,
  "paid": 200,
  "mobile": "9876543210"
}
```

---

## Useful MySQL Queries (Manual Checks)

```sql
USE iskcon_ramnavmi_db;

-- Total registered families and persons
SELECT COUNT(*) AS families, SUM(persons) AS total_persons FROM registrations;

-- Total attended and persons counted at gate
SELECT COUNT(*) AS families, SUM(persons) AS persons_at_event FROM attendance;

-- Total money collected
SELECT SUM(paid) AS total_collected FROM attendance;

-- Full combined report
SELECT r.token, r.name, r.persons AS members,
       r.paid, r.reg_at,
       IF(a.id IS NOT NULL,'YES','NO') AS attended,
       a.gate_time
FROM registrations r
LEFT JOIN attendance a ON r.token = a.token
ORDER BY r.id;

-- Families not yet arrived
SELECT r.token, r.name, r.mobile, r.persons
FROM registrations r
LEFT JOIN attendance a ON r.token = a.token
WHERE a.id IS NULL;
```

---

## Clearing All Data (End of Event / Testing)

**Via API:**
```bash
curl -X POST http://localhost:5000/api/admin/clear \
  -H "Content-Type: application/json" \
  -d "{\"secret\":\"ISKCON_CLEAR_CONFIRM_2025\"}"
```

**Via MySQL:**
```sql
USE iskcon_ramnavmi_db;
DELETE FROM attendance;
DELETE FROM registrations;
UPDATE token_counter SET current = 0 WHERE id = 1;
```

> **Warning:** This permanently deletes all registration and attendance data. Export the CSV first if you need to keep records.

---

## Troubleshooting

**"Server Offline" shown in the header**
- Flask server is not running — run `python app.py`

**Phone cannot connect to the server**
- Phone and PC must be on the **same WiFi network**
- Check the IP in `index.html` matches your `ipconfig` output
- Allow port 5000 in Windows Firewall (see Step 9)

**MySQL connection error on startup**
- Check `user` and `password` in `app.py` DB_CONFIG
- Ensure MySQL service is running: `sudo systemctl start mysql` (Linux) or check Services (Windows)
- Try connecting manually: `mysql -u root -p`

**Camera not working on phone**
- Chrome requires HTTPS for camera access on non-localhost devices
- **Workaround:** Use the **"Fill Token Manually"** option at the gate
- **Alternative:** Set up ngrok for HTTPS: `ngrok http 5000` and use the HTTPS URL

**Token numbers reset after restart**
- This is normal — token numbers are stored in MySQL, not in memory. They persist across restarts.

**Duplicate token error on registration**
- The `token_counter` table ensures atomic increments; this should not happen under normal use. If the database was manually edited, reset the counter: `UPDATE token_counter SET current = (SELECT MAX(CAST(token AS UNSIGNED)) FROM registrations) WHERE id = 1;`

---

## Data Flow Summary

```
[Invite QR displayed on Admin PC]
         ↓
[Family scans QR on their phone]
         ↓
[Fills registration form → POST /api/register]
         ↓
[MySQL: INSERT into registrations, token = 001,002,...]
         ↓
[Family receives unique QR with their token]
         ↓
[Gate volunteer scans family QR → POST /api/gate/scan]
         ↓
[MySQL: INSERT into attendance]
         ↓
[Dashboard polls /api/stats every 5 sec → shows live counts]
```

---

## Quick Start Checklist

- [ ] Python 3.8+ installed
- [ ] `pip install -r requirements.txt` done
- [ ] MySQL running and schema imported (`mysql -u root -p < schema.sql`)
- [ ] DB credentials updated in `app.py`
- [ ] LAN IP found and updated in `index.html`
- [ ] UPI ID updated in `index.html`
- [ ] Windows Firewall allows port 5000
- [ ] `python app.py` running — status shows **Server Online**
- [ ] Invite QR printed / displayed for families
- [ ] Gate device opened on `http://<YOUR_IP>:5000` → Gate Scan tab

---

Hare Krishna · Jai Shri Ram
