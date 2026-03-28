# ============================================================
#  DEVOTEE GATHERING SYSTEM — Flask Backend API
#  File: app.py
#
#  Install dependencies:
#    pip install flask flask-cors pymysql
#
#  Run:
#    python app.py
#
#  All devices on same WiFi connect to:
#    http://<YOUR_PC_IP>:5000
# ============================================================

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import pymysql
import pymysql.cursors
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)  # Allow all origins — devices on LAN can call this API

# ── LOGGING ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s'
)
log = logging.getLogger(__name__)

# ============================================================
#  DATABASE CONFIG — Edit these values
# ============================================================
DB_CONFIG = {
    'host':     'localhost',
    'port':     3306,
    'user':     'root',          # ← your MySQL username
    'password': 'root',  # ← your MySQL password
    'db':       'iskcon_ramnavmi_db',
    'charset':  'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True,
}
# ============================================================

def get_db():
    """Open a fresh DB connection per request."""
    return pymysql.connect(**DB_CONFIG)


def db_query(sql, args=None, fetch='all'):
    """Helper: run a query, return results."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            if fetch == 'all':
                return cur.fetchall()
            elif fetch == 'one':
                return cur.fetchone()
            else:
                conn.commit()
                return cur.rowcount
    finally:
        conn.close()


def db_execute(sql, args=None):
    """Helper: run INSERT/UPDATE/DELETE."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


# ============================================================
#  HEALTH CHECK
# ============================================================
@app.route('/')
@app.route('/index.html')
def serve_frontend():
    """Serve the registration HTML frontend directly from Flask.
    This means the invitation QR can point to http://YOUR_IP:5000/?register=1
    and the phone opens the form immediately — no separate HTTP server needed.
    """
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/api/ping', methods=['GET'])
def ping():
    """Quick health check — frontend polls this on load."""
    try:
        db_query("SELECT 1", fetch='one')
        return jsonify({'status': 'ok', 'message': 'ISKCON Ram Navmi API is running'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================================
#  STATS — summary numbers for admin & dashboard
# ============================================================
@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        reg_row = db_query(
            "SELECT COUNT(*) AS families, COALESCE(SUM(persons),0) AS persons FROM registrations",
            fetch='one'
        )
        att_row = db_query(
            "SELECT COUNT(*) AS families, COALESCE(SUM(persons),0) AS persons, COALESCE(SUM(paid),0) AS collection FROM attendance",
            fetch='one'
        )
        return jsonify({
            'registered_families': reg_row['families'],
            'registered_persons':  int(reg_row['persons']),
            'attended_families':   att_row['families'],
            'attended_persons':    int(att_row['persons']),
            'collection':          int(att_row['collection']),
            'pending_families':    max(0, reg_row['families'] - att_row['families']),
        })
    except Exception as e:
        log.error(f'stats error: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================================
#  REGISTRATIONS
# ============================================================
@app.route('/api/registrations', methods=['GET'])
def list_registrations():
    """Return all registrations, newest first, with attended flag."""
    try:
        rows = db_query("""
            SELECT r.*,
                   IF(a.token IS NOT NULL, 1, 0) AS attended,
                   a.gate_time
            FROM registrations r
            LEFT JOIN attendance a ON r.token = a.token
            ORDER BY r.id DESC
        """)
        # Serialize datetime objects
        for row in rows:
            if row.get('reg_at'):
                row['reg_at'] = row['reg_at'].strftime('%d/%m/%Y %H:%M')
            if row.get('gate_time'):
                row['gate_time'] = row['gate_time'].strftime('%d/%m/%Y %H:%M')
        return jsonify({'registrations': rows})
    except Exception as e:
        log.error(f'list_registrations error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/register', methods=['POST'])
def register_family():
    """
    Register a family.
    Body JSON: { name, address, mobile, persons, paid }
    Returns: { token, ... }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data sent'}), 400

    name    = str(data.get('name', '')).strip()
    address = str(data.get('address', '')).strip()
    mobile  = str(data.get('mobile', '')).strip()
    persons = int(data.get('persons', 1))
    paid    = int(data.get('paid', 0))

    # Validate
    if not name or not address or not mobile:
        return jsonify({'error': 'name, address, mobile are required'}), 400
    if persons < 1 or persons > 50:
        return jsonify({'error': 'persons must be 1–50'}), 400

    try:
        # Get next token number (atomic increment)
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE token_counter SET current = current + 1 WHERE id = 1"
                )
                cur.execute("SELECT current FROM token_counter WHERE id = 1")
                tok_num = cur.fetchone()['current']
                token = str(tok_num).zfill(3)   # 001, 002, ...

                cur.execute("""
                    INSERT INTO registrations (token, name, address, mobile, persons, paid)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (token, name, address, mobile, persons, paid))
                conn.commit()
        finally:
            conn.close()

        log.info(f'Registered: token={token} name={name} persons={persons} paid={paid}')
        return jsonify({
            'success': True,
            'token': token,
            'name': name,
            'persons': persons,
            'paid': paid,
            'reg_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
        }), 201

    except Exception as e:
        log.error(f'register error: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================================
#  ATTENDANCE (Gate)
# ============================================================
@app.route('/api/attendance', methods=['GET'])
def list_attendance():
    """Return all attendance records, latest first."""
    try:
        rows = db_query("""
            SELECT * FROM attendance
            ORDER BY gate_time DESC
        """)
        for row in rows:
            if row.get('gate_time'):
                row['gate_time'] = row['gate_time'].strftime('%d/%m/%Y %H:%M')
        return jsonify({'attendance': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/attendance/hourly', methods=['GET'])
def hourly_attendance():
    """Return count of family entries per hour (for dashboard chart)."""
    try:
        rows = db_query("""
            SELECT HOUR(gate_time) AS hr, COUNT(*) AS families, SUM(persons) AS persons
            FROM attendance
            WHERE DATE(gate_time) = CURDATE()
            GROUP BY HOUR(gate_time)
            ORDER BY hr
        """)
        # Build 8–20 slots
        slots = {h: {'families': 0, 'persons': 0} for h in range(8, 21)}
        for row in rows:
            h = int(row['hr'])
            if h in slots:
                slots[h] = {'families': int(row['families']), 'persons': int(row['persons'])}
        return jsonify({'hourly': slots})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gate/scan', methods=['POST'])
def gate_scan():
    """
    Gate volunteer scans family QR.
    Body JSON: { token, name, persons, paid, mobile }
    Returns: success/duplicate/error
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data sent'}), 400

    token   = str(data.get('token', '')).strip()
    name    = str(data.get('name', '')).strip()
    persons = int(data.get('persons', 1))
    paid    = int(data.get('paid', 0))
    mobile  = str(data.get('mobile', '')).strip()

    if not token:
        return jsonify({'error': 'token is required'}), 400

    try:
        # Check if already attended
        existing = db_query(
            "SELECT * FROM attendance WHERE token = %s", (token,), fetch='one'
        )
        if existing:
            gate_time = existing['gate_time']
            if hasattr(gate_time, 'strftime'):
                gate_time = gate_time.strftime('%H:%M')
            return jsonify({
                'status': 'duplicate',
                'message': f'Already entered at {gate_time}',
                'token': token,
                'name': name,
                'persons': existing['persons'],
                'gate_time': gate_time,
            }), 200

        # Check token exists in registrations
        reg = db_query(
            "SELECT * FROM registrations WHERE token = %s", (token,), fetch='one'
        )
        if not reg:
            return jsonify({
                'status': 'not_found',
                'message': 'Token not found in registrations. QR may be invalid.',
            }), 404

        # ── MARK ATTENDANCE ──
        # persons = ALL family members counted in this single scan
        db_execute("""
            INSERT INTO attendance (token, name, persons, paid, mobile)
            VALUES (%s, %s, %s, %s, %s)
        """, (token, name, persons, paid, mobile))

        now_str = datetime.now().strftime('%H:%M')
        log.info(f'Gate entry: token={token} name={name} persons={persons}')
        return jsonify({
            'status': 'success',
            'message': f'Family entry granted. {persons} member(s) counted.',
            'token': token,
            'name': name,
            'persons': persons,
            'paid': paid,
            'gate_time': now_str,
        }), 200

    except Exception as e:
        log.error(f'gate_scan error: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================================
#  EXPORT — CSV download
# ============================================================
@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Download full report as CSV."""
    try:
        rows = db_query("""
            SELECT
                r.token,
                r.name,
                r.address,
                r.mobile,
                r.persons AS registered_members,
                r.paid,
                r.reg_at,
                IF(a.token IS NOT NULL,'Yes','No') AS attended,
                COALESCE(a.persons, 0)             AS members_counted,
                COALESCE(DATE_FORMAT(a.gate_time,'%%d/%%m/%%Y %%H:%%i'), '') AS gate_time
            FROM registrations r
            LEFT JOIN attendance a ON r.token = a.token
            ORDER BY r.id ASC
        """)

        lines = ['Token,Family Head,Address,Mobile,Members,Paid(Rs),Registered At,Attended,Members Counted,Gate Entry Time']
        for r in rows:
            addr = str(r['address']).replace(',', ';').replace('\n', ' ')
            reg_at = r['reg_at'].strftime('%d/%m/%Y %H:%M') if hasattr(r['reg_at'], 'strftime') else r['reg_at']
            lines.append(
                f"{r['token']},{r['name']},{addr},{r['mobile']},"
                f"{r['registered_members']},{r['paid']},{reg_at},"
                f"{r['attended']},{r['members_counted']},{r['gate_time']}"
            )

        from flask import Response
        return Response(
            '\n'.join(lines),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=iskcon_ramnavmi_report.csv'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
#  ADMIN — Reset / Clear
# ============================================================
@app.route('/api/admin/clear', methods=['POST'])
def clear_all():
    """Clear all data (admin only — use with caution!)."""
    secret = request.get_json().get('secret', '')
    if secret != 'ISKCON_CLEAR_CONFIRM_2025':   # simple guard
        return jsonify({'error': 'Invalid confirmation secret'}), 403
    try:
        db_execute("DELETE FROM attendance")
        db_execute("DELETE FROM registrations")
        db_execute("UPDATE token_counter SET current = 0 WHERE id = 1")
        log.warning('ALL DATA CLEARED by admin')
        return jsonify({'success': True, 'message': 'All data cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
#  RUN
# ============================================================
if __name__ == '__main__':
    import socket
    # Show LAN IP so you know what to share with other devices
    hostname = socket.gethostname()
    try:
        lan_ip = socket.gethostbyname(hostname)
    except Exception:
        lan_ip = '127.0.0.1'

    print('\n' + '='*55)
    print('  🕉  ISKCON SOCIETY — RAM NAVMI CELEBRATION 2025')
    print('='*55)
    print(f'  Local:   http://localhost:5000')
    print(f'  Network: http://{lan_ip}:5000')
    print(f'  Health:  http://{lan_ip}:5000/api/ping')
    print(f'  QR URL:  http://{lan_ip}:5000/?register=1')
    print('='*55)
    print('  Share the Network URL with:')
    print('  • Registration device (any phone/tablet on WiFi)')
    print('  • Gate device (volunteer\'s phone)')
    print('  • Admin/Dashboard device (laptop)')
    print('='*55 + '\n')

    app.run(
        host='0.0.0.0',   # Listen on all network interfaces
        port=int(os.environ.get('PORT', 5000)),
        debug=False,       # Set True during development
    )
