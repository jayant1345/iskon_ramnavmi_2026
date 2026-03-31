# ============================================================
#  DEVOTEE GATHERING SYSTEM — Flask Backend API
#  File: app.py
# ============================================================

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import re
import secrets
import pymysql
import pymysql.cursors
from datetime import datetime, timedelta
import logging

app = Flask(__name__)

# ── SECRET KEY (set SECRET_KEY env var on Railway) ──
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    # SESSION_COOKIE_SECURE=True on Railway (HTTPS), but allow HTTP for local dev
    SESSION_COOKIE_SECURE=os.environ.get('RAILWAY_ENVIRONMENT') is not None,
)

# Allow credentials with CORS (needed for session cookies)
CORS(app, supports_credentials=True, origins=[
    'https://iskonramnavmi2026-production.up.railway.app',
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://localhost:8012',
    'http://127.0.0.1:8012',
])

# ── LOGGING ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s'
)
log = logging.getLogger(__name__)

# ============================================================
#  DATABASE CONFIG
# ============================================================
DB_CONFIG = {
    'host':     os.environ.get('MYSQLHOST', 'localhost'),
    'port':     int(os.environ.get('MYSQLPORT') or 3306),
    'user':     os.environ.get('MYSQLUSER', 'root'),
    'password': os.environ.get('MYSQLPASSWORD', 'root'),
    'db':       os.environ.get('MYSQL_DATABASE', 'iskcon_ramnavmi_db'),
    'charset':  'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True,
}

def get_db():
    return pymysql.connect(**DB_CONFIG)


def init_db():
    try:
        conn = pymysql.connect(**DB_CONFIG)
    except Exception as e:
        log.error(f'init_db: cannot connect to DB at startup: {e}')
        return
    try:
        with conn.cursor() as cur:
            # ── USERS table ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    username      VARCHAR(50)   NOT NULL UNIQUE,
                    password_hash VARCHAR(256)  NOT NULL,
                    name          VARCHAR(150)  NOT NULL,
                    mobile        VARCHAR(15)   NOT NULL,
                    role          ENUM('admin','user') NOT NULL DEFAULT 'user',
                    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_username (username)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)

            # ── REGISTRATIONS table ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id      INT AUTO_INCREMENT PRIMARY KEY,
                    token   VARCHAR(10)  NOT NULL UNIQUE,
                    name    VARCHAR(150) NOT NULL,
                    address TEXT         NOT NULL,
                    mobile  VARCHAR(15)  NOT NULL,
                    persons INT          NOT NULL DEFAULT 1,
                    paid    INT          NOT NULL DEFAULT 0,
                    free_entry TINYINT(1) NOT NULL DEFAULT 0,
                    registered_by INT    NULL,
                    reg_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_token (token),
                    INDEX idx_mobile (mobile),
                    INDEX idx_reg_by (registered_by)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)

            # ── ATTENDANCE table ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id        INT AUTO_INCREMENT PRIMARY KEY,
                    token     VARCHAR(10)  NOT NULL UNIQUE,
                    name      VARCHAR(150) NOT NULL,
                    persons   INT          NOT NULL DEFAULT 1,
                    paid      INT          NOT NULL DEFAULT 0,
                    mobile    VARCHAR(15),
                    gate_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (token) REFERENCES registrations(token) ON DELETE CASCADE,
                    INDEX idx_token (token)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4
            """)

            # ── TOKEN COUNTER ──
            cur.execute("""
                CREATE TABLE IF NOT EXISTS token_counter (
                    id      INT PRIMARY KEY DEFAULT 1,
                    current INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB
            """)
            cur.execute("INSERT IGNORE INTO token_counter (id, current) VALUES (1, 0)")

            # ── Safe migrations: add columns if not present ──
            for col_sql, col_name in [
                ("ALTER TABLE registrations ADD COLUMN registered_by INT NULL", "registered_by"),
                ("ALTER TABLE registrations ADD COLUMN free_entry TINYINT(1) NOT NULL DEFAULT 0", "free_entry"),
            ]:
                try:
                    cur.execute("""
                        SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'registrations'
                          AND COLUMN_NAME = %s
                    """, (col_name,))
                    if cur.fetchone()['cnt'] == 0:
                        cur.execute(col_sql)
                        log.info(f'Migration: added column {col_name}')
                except Exception as me:
                    log.error(f'Migration error ({col_name}): {me}')

            # ── Seed default admin user (INSERT IGNORE = only once) ──
            admin_pw = os.environ.get('ADMIN_PASSWORD', 'admin123')
            cur.execute("""
                INSERT IGNORE INTO users (username, password_hash, name, mobile, role)
                VALUES (%s, %s, %s, %s, 'admin')
            """, ('admin', generate_password_hash(admin_pw), 'Administrator', os.environ.get('ADMIN_MOBILE', '0000000000')))

            conn.commit()
        log.info('Database tables ready.')
    except Exception as e:
        log.error(f'init_db error: {e}')
    finally:
        conn.close()


init_db()


# ============================================================
#  DB HELPERS
# ============================================================
def db_query(sql, args=None, fetch='all'):
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
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


# ============================================================
#  AUTH DECORATORS
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated', 'code': 'AUTH_REQUIRED'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated', 'code': 'AUTH_REQUIRED'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required', 'code': 'FORBIDDEN'}), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================
#  STATIC FILES
# ============================================================
@app.route('/')
@app.route('/index.html')
def serve_frontend():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/logo.png')
def serve_logo():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'logo.png')


# ============================================================
#  HEALTH CHECK  (public — no auth needed)
# ============================================================
@app.route('/api/ping', methods=['GET'])
def ping():
    try:
        db_query("SELECT 1", fetch='one')
        return jsonify({'status': 'ok', 'message': 'ISKCON Ram Navmi API is running'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================================
#  AUTH ROUTES
# ============================================================
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data sent'}), 400
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    user = db_query("SELECT * FROM users WHERE username = %s", (username,), fetch='one')
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    session.clear()
    session.permanent = True
    session['user_id']  = user['id']
    session['username'] = user['username']
    session['name']     = user['name']
    session['mobile']   = user['mobile']
    session['role']     = user['role']
    log.info(f"Login: {username} ({user['role']})")
    return jsonify({
        'success': True,
        'user': {
            'id':       user['id'],
            'username': user['username'],
            'name':     user['name'],
            'mobile':   user['mobile'],
            'upi_id':   user['mobile'] + '@upi',
            'role':     user['role'],
        }
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    log.info(f"Logout: {session.get('username', '?')}")
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 200
    return jsonify({
        'authenticated': True,
        'user': {
            'id':       session['user_id'],
            'username': session['username'],
            'name':     session['name'],
            'mobile':   session['mobile'],
            'upi_id':   session['mobile'] + '@upi',
            'role':     session['role'],
        }
    })


# ============================================================
#  USER MANAGEMENT  (admin only)
# ============================================================
@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    users = db_query(
        "SELECT id, username, name, mobile, role, created_at FROM users ORDER BY id"
    )
    for u in users:
        u['upi_id'] = u['mobile'] + '@upi'
        if u.get('created_at'):
            u['created_at'] = u['created_at'].strftime('%d/%m/%Y %H:%M')
    return jsonify({'users': users})


@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json()
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))
    name     = str(data.get('name', '')).strip()
    mobile   = str(data.get('mobile', '')).strip()
    role     = data.get('role', 'user')
    if not all([username, password, name, mobile]):
        return jsonify({'error': 'All fields are required'}), 400
    if role not in ('admin', 'user'):
        return jsonify({'error': 'Invalid role'}), 400
    if not re.match(r'^\d{10}$', mobile):
        return jsonify({'error': 'Mobile must be exactly 10 digits'}), 400
    try:
        uid = db_execute(
            "INSERT INTO users (username, password_hash, name, mobile, role) VALUES (%s,%s,%s,%s,%s)",
            (username, generate_password_hash(password), name, mobile, role)
        )
        log.info(f'Created user: {username} role={role}')
        return jsonify({'success': True, 'id': uid}), 201
    except Exception as e:
        if 'Duplicate entry' in str(e):
            return jsonify({'error': 'Username already exists'}), 409
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<int:uid>', methods=['PUT'])
@admin_required
def update_user(uid):
    data = request.get_json()
    name   = str(data.get('name', '')).strip()
    mobile = str(data.get('mobile', '')).strip()
    role   = data.get('role', 'user')
    if not name or not mobile:
        return jsonify({'error': 'Name and mobile are required'}), 400
    if role not in ('admin', 'user'):
        return jsonify({'error': 'Invalid role'}), 400
    if not re.match(r'^\d{10}$', mobile):
        return jsonify({'error': 'Mobile must be exactly 10 digits'}), 400
    if data.get('password'):
        db_execute(
            "UPDATE users SET name=%s, mobile=%s, role=%s, password_hash=%s WHERE id=%s",
            (name, mobile, role, generate_password_hash(data['password']), uid)
        )
    else:
        db_execute(
            "UPDATE users SET name=%s, mobile=%s, role=%s WHERE id=%s",
            (name, mobile, role, uid)
        )
    log.info(f'Updated user id={uid}')
    return jsonify({'success': True})


@app.route('/api/users/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    # Prevent deleting the only admin
    admins = db_query("SELECT id FROM users WHERE role='admin'")
    if len(admins) == 1 and admins[0]['id'] == uid:
        return jsonify({'error': 'Cannot delete the only admin account'}), 400
    db_execute("DELETE FROM users WHERE id=%s", (uid,))
    log.info(f'Deleted user id={uid}')
    return jsonify({'success': True})


# ============================================================
#  STATS
# ============================================================
@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    try:
        reg_row = db_query(
            "SELECT COUNT(*) AS families, COALESCE(SUM(persons),0) AS persons, COALESCE(SUM(paid),0) AS collection FROM registrations",
            fetch='one'
        )
        att_row = db_query(
            "SELECT COUNT(*) AS families, COALESCE(SUM(persons),0) AS persons FROM attendance",
            fetch='one'
        )
        result = {
            'registered_families': reg_row['families'],
            'registered_persons':  int(reg_row['persons']),
            'attended_families':   att_row['families'],
            'attended_persons':    int(att_row['persons']),
            'pending_families':    max(0, reg_row['families'] - att_row['families']),
        }
        # Collection visible to admin only
        if session.get('role') == 'admin':
            result['collection'] = int(reg_row['collection'])
        return jsonify(result)
    except Exception as e:
        log.error(f'stats error: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/user-stats', methods=['GET'])
@admin_required
def user_stats():
    try:
        rows = db_query("""
            SELECT
                u.id,
                u.name,
                u.username,
                u.mobile,
                COUNT(r.id)                   AS families_registered,
                COALESCE(SUM(r.persons), 0)   AS persons_registered,
                COALESCE(SUM(r.paid), 0)      AS collection
            FROM users u
            LEFT JOIN registrations r ON r.registered_by = u.id
            GROUP BY u.id
            ORDER BY collection DESC
        """)
        for row in rows:
            row['families_registered'] = int(row['families_registered'])
            row['persons_registered']  = int(row['persons_registered'])
            row['collection']          = int(row['collection'])
        return jsonify({'user_stats': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/my-stats', methods=['GET'])
@login_required
def my_stats():
    try:
        uid = session['user_id']
        row = db_query("""
            SELECT COUNT(*) AS families, COALESCE(SUM(persons),0) AS persons
            FROM registrations WHERE registered_by = %s
        """, (uid,), fetch='one')
        return jsonify({'families': row['families'], 'persons': int(row['persons'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
#  REGISTRATIONS
# ============================================================
@app.route('/api/registrations', methods=['GET'])
@login_required
def list_registrations():
    try:
        rows = db_query("""
            SELECT r.*,
                   IF(a.token IS NOT NULL, 1, 0) AS attended,
                   a.gate_time,
                   u.name AS registered_by_name,
                   u.username AS registered_by_username
            FROM registrations r
            LEFT JOIN attendance a ON r.token = a.token
            LEFT JOIN users u ON u.id = r.registered_by
            ORDER BY r.id DESC
        """)
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
@login_required
def register_family():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data sent'}), 400

    name       = str(data.get('name', '')).strip()
    address    = str(data.get('address', '')).strip()
    mobile     = str(data.get('mobile', '')).strip()
    persons    = int(data.get('persons', 1))
    free_entry = bool(data.get('free_entry', False))
    paid       = 0 if free_entry else int(data.get('paid', 0))
    registered_by = session['user_id']

    if not name or not address or not mobile:
        return jsonify({'error': 'name, address, mobile are required'}), 400
    if persons < 1 or persons > 50:
        return jsonify({'error': 'persons must be 1–50'}), 400

    try:
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE token_counter SET current = current + 1 WHERE id = 1")
                cur.execute("SELECT current FROM token_counter WHERE id = 1")
                tok_num = cur.fetchone()['current']
                token = str(tok_num).zfill(3)

                cur.execute("""
                    INSERT INTO registrations (token, name, address, mobile, persons, paid, free_entry, registered_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (token, name, address, mobile, persons, paid, int(free_entry), registered_by))
                conn.commit()
        finally:
            conn.close()

        log.info(f'Registered: token={token} name={name} persons={persons} paid={paid} free={free_entry} by=user{registered_by}')
        return jsonify({
            'success':    True,
            'token':      token,
            'name':       name,
            'persons':    persons,
            'paid':       paid,
            'free_entry': free_entry,
            'reg_at':     datetime.now().strftime('%d/%m/%Y %H:%M'),
        }), 201

    except Exception as e:
        log.error(f'register error: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================================
#  ATTENDANCE (Gate)
# ============================================================
@app.route('/api/attendance', methods=['GET'])
@login_required
def list_attendance():
    try:
        rows = db_query("SELECT * FROM attendance ORDER BY gate_time DESC")
        for row in rows:
            if row.get('gate_time'):
                row['gate_time'] = row['gate_time'].strftime('%d/%m/%Y %H:%M')
        return jsonify({'attendance': rows})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/attendance/hourly', methods=['GET'])
@login_required
def hourly_attendance():
    try:
        rows = db_query("""
            SELECT HOUR(gate_time) AS hr, COUNT(*) AS families, SUM(persons) AS persons
            FROM attendance
            WHERE DATE(gate_time) = CURDATE()
            GROUP BY HOUR(gate_time)
            ORDER BY hr
        """)
        slots = {h: {'families': 0, 'persons': 0} for h in range(8, 21)}
        for row in rows:
            h = int(row['hr'])
            if h in slots:
                slots[h] = {'families': int(row['families']), 'persons': int(row['persons'])}
        return jsonify({'hourly': slots})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gate/scan', methods=['POST'])
@login_required
def gate_scan():
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
        existing = db_query("SELECT * FROM attendance WHERE token = %s", (token,), fetch='one')
        if existing:
            gate_time = existing['gate_time']
            if hasattr(gate_time, 'strftime'):
                gate_time = gate_time.strftime('%H:%M')
            reg = db_query("SELECT * FROM registrations WHERE token = %s", (token,), fetch='one')
            registered_total = reg['persons'] if reg else existing['persons']
            already_in = existing['persons']
            remaining = max(0, registered_total - already_in)
            if persons > 0 and data.get('add_more'):
                new_total = already_in + persons
                db_execute("UPDATE attendance SET persons = %s WHERE token = %s", (new_total, token))
                log.info(f'Added {persons} more for token={token}, total={new_total}')
                return jsonify({
                    'status':    'success',
                    'message':   f'{persons} more member(s) added. Total: {new_total}',
                    'token':     token,
                    'name':      name,
                    'persons':   new_total,
                    'gate_time': gate_time,
                }), 200
            return jsonify({
                'status':     'duplicate',
                'message':    f'Already entered at {gate_time}',
                'token':      token,
                'name':       name,
                'persons':    already_in,
                'registered': registered_total,
                'remaining':  remaining,
                'gate_time':  gate_time,
            }), 200

        reg = db_query("SELECT * FROM registrations WHERE token = %s", (token,), fetch='one')
        if not reg:
            return jsonify({'status': 'not_found', 'message': 'Token not found in registrations.'}), 404

        db_execute("""
            INSERT INTO attendance (token, name, persons, paid, mobile)
            VALUES (%s, %s, %s, %s, %s)
        """, (token, name, persons, paid, mobile))

        now_str = datetime.now().strftime('%H:%M')
        log.info(f'Gate entry: token={token} name={name} persons={persons}')
        return jsonify({
            'status':    'success',
            'message':   f'Family entry granted. {persons} member(s) counted.',
            'token':     token,
            'name':      name,
            'persons':   persons,
            'paid':      paid,
            'gate_time': now_str,
        }), 200

    except Exception as e:
        log.error(f'gate_scan error: {e}')
        return jsonify({'error': str(e)}), 500


# ============================================================
#  EXPORT CSV
# ============================================================
@app.route('/api/export/csv', methods=['GET'])
@login_required
def export_csv():
    try:
        rows = db_query("""
            SELECT
                r.token,
                r.name,
                r.address,
                r.mobile,
                r.persons AS registered_members,
                r.paid,
                r.free_entry,
                r.reg_at,
                COALESCE(u.name, 'Unknown')   AS registered_by_user,
                IF(a.token IS NOT NULL,'Yes','No') AS attended,
                COALESCE(a.persons, 0)             AS members_counted,
                COALESCE(DATE_FORMAT(a.gate_time,'%%d/%%m/%%Y %%H:%%i'), '') AS gate_time
            FROM registrations r
            LEFT JOIN users u ON u.id = r.registered_by
            LEFT JOIN attendance a ON r.token = a.token
            ORDER BY r.id ASC
        """)

        lines = ['Token,Family Head,Address,Mobile,Members,Paid(Rs),Free Entry,Registered At,Registered By,Attended,Members Counted,Gate Entry Time']
        for r in rows:
            addr   = str(r['address']).replace(',', ';').replace('\n', ' ')
            reg_at = r['reg_at'].strftime('%d/%m/%Y %H:%M') if hasattr(r['reg_at'], 'strftime') else r['reg_at']
            lines.append(
                f"{r['token']},{r['name']},{addr},{r['mobile']},"
                f"{r['registered_members']},{r['paid']},{'Yes' if r['free_entry'] else 'No'},"
                f"{reg_at},{r['registered_by_user']},"
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
@admin_required
def clear_all():
    secret = request.get_json().get('secret', '')
    if secret != 'ISKCON_CLEAR_CONFIRM_2026':
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
    hostname = socket.gethostname()
    try:
        lan_ip = socket.gethostbyname(hostname)
    except Exception:
        lan_ip = '127.0.0.1'

    port = int(os.environ.get('PORT', 5000))
    print('\n' + '='*55)
    print('  🕉  ISKCON SOCIETY — RAM NAVMI CELEBRATION 2026')
    print('='*55)
    print(f'  Local:   http://localhost:{port}')
    print(f'  Network: http://{lan_ip}:{port}')
    print(f'  Default login: admin / admin123')
    print('='*55 + '\n')

    app.run(host='0.0.0.0', port=port, debug=False)
