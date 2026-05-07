from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta, timezone
import os
import argparse

app = Flask(__name__, static_folder='static')
CORS(app)

DB_PATH = 'presence.db'

def local_to_utc(local_dt):
    """Convert naive local datetime to naive UTC datetime"""
    # Calculate the offset between local time and UTC
    now_local = datetime.now()
    now_utc = datetime.utcnow()
    offset = now_local - now_utc

    # Subtract the offset to get UTC time
    return local_dt - offset

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS presence_beeps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_username_timestamp
        ON presence_beeps(username, timestamp)
    ''')

    conn.commit()
    conn.close()

def calculate_sessions(beeps):
    """
    Calculate work sessions from beeps.
    Beeps within 2 minutes of each other are considered part of the same session.
    """
    if not beeps:
        return []

    sessions = []
    current_session_start = None
    last_beep_time = None

    for beep_time in beeps:
        beep_dt = datetime.fromisoformat(beep_time)

        if current_session_start is None:
            current_session_start = beep_dt
            last_beep_time = beep_dt
        else:
            time_diff = (beep_dt - last_beep_time).total_seconds()

            if time_diff > 120:  # More than 2 minutes gap
                sessions.append({
                    'start': current_session_start.isoformat(),
                    'end': last_beep_time.isoformat(),
                    'duration_minutes': (last_beep_time - current_session_start).total_seconds() / 60
                })
                current_session_start = beep_dt

            last_beep_time = beep_dt

    # Add the final session
    if current_session_start and last_beep_time:
        sessions.append({
            'start': current_session_start.isoformat(),
            'end': last_beep_time.isoformat(),
            'duration_minutes': (last_beep_time - current_session_start).total_seconds() / 60
        })

    return sessions

@app.route('/beep', methods=['POST', 'GET'])
def record_beep():
    """Record a presence beep from a user"""
    if request.method == 'POST':
        data = request.get_json() or {}
        user = data.get('user')
    else:  # GET
        user = request.args.get('user')

    if not user:
        return jsonify({'error': 'user is required'}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        'INSERT INTO presence_beeps (username, timestamp) VALUES (?, ?)',
        (user, datetime.utcnow().isoformat() + 'Z')
    )

    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'user': user}), 200

@app.route('/users', methods=['GET'])
def get_users():
    """Get list of all users"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT username FROM presence_beeps ORDER BY username')
    users = [row[0] for row in cursor.fetchall()]

    conn.close()

    return jsonify({'users': users})

@app.route('/stats/<username>', methods=['GET'])
def get_user_stats(username):
    """Get work statistics for a user"""
    period = request.args.get('period', 'day')  # day, month, or year
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    # Handle YYYY-MM-DD (day), YYYY-MM (month), and YYYY (year) formats
    try:
        if period == 'year' and len(date_str) == 4:  # YYYY format
            target_date = datetime.strptime(date_str, '%Y')
        elif period == 'month' and len(date_str) == 7:  # YYYY-MM format
            target_date = datetime.strptime(date_str, '%Y-%m')
        else:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD for day, YYYY-MM for month, or YYYY for year'}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if period == 'day':
        start_date_local = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_local = start_date_local + timedelta(days=1)

        # Convert to UTC for database query
        start_date = local_to_utc(start_date_local)
        end_date = local_to_utc(end_date_local)

        cursor.execute(
            'SELECT timestamp FROM presence_beeps WHERE username = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp',
            (username, start_date.isoformat() + 'Z', end_date.isoformat() + 'Z')
        )
    elif period == 'month':
        start_date_local = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if target_date.month == 12:
            end_date_local = start_date_local.replace(year=start_date_local.year + 1, month=1)
        else:
            end_date_local = start_date_local.replace(month=start_date_local.month + 1)

        # Convert to UTC for database query
        start_date = local_to_utc(start_date_local)
        end_date = local_to_utc(end_date_local)

        cursor.execute(
            'SELECT timestamp FROM presence_beeps WHERE username = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp',
            (username, start_date.isoformat() + 'Z', end_date.isoformat() + 'Z')
        )
    else:  # year
        start_date_local = target_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date_local = start_date_local.replace(year=start_date_local.year + 1)

        # Convert to UTC for database query
        start_date = local_to_utc(start_date_local)
        end_date = local_to_utc(end_date_local)

        cursor.execute(
            'SELECT timestamp FROM presence_beeps WHERE username = ? AND timestamp >= ? AND timestamp < ? ORDER BY timestamp',
            (username, start_date.isoformat() + 'Z', end_date.isoformat() + 'Z')
        )

    beeps = [row[0] for row in cursor.fetchall()]
    conn.close()

    if period == 'day':
        sessions = calculate_sessions(beeps)
        # Calculate total hours based on beep count (1 beep = 1 minute)
        total_hours = len(beeps) / 60

        return jsonify({
            'user': username,
            'date': date_str,
            'period': period,
            'total_hours': round(total_hours, 2),
            'total_minutes': len(beeps),
            'sessions': sessions,
            'beep_count': len(beeps)
        })
    elif period == 'month':
        # Group by day
        daily_stats = {}
        for beep in beeps:
            beep_date = datetime.fromisoformat(beep).strftime('%Y-%m-%d')
            if beep_date not in daily_stats:
                daily_stats[beep_date] = []
            daily_stats[beep_date].append(beep)

        days = []
        total_month_minutes = 0
        for day, day_beeps in sorted(daily_stats.items()):
            sessions = calculate_sessions(day_beeps)
            day_minutes = len(day_beeps)
            day_hours = day_minutes / 60
            total_month_minutes += day_minutes
            days.append({
                'date': day,
                'hours': round(day_hours, 2),
                'minutes': day_minutes,
                'beep_count': len(day_beeps),
                'sessions': sessions
            })

        return jsonify({
            'user': username,
            'period': period,
            'month': start_date.strftime('%Y-%m'),
            'total_hours': round(total_month_minutes / 60, 2),
            'total_minutes': total_month_minutes,
            'days': days
        })
    else:  # year
        # Group by month
        monthly_stats = {}
        for beep in beeps:
            beep_month = datetime.fromisoformat(beep).strftime('%Y-%m')
            if beep_month not in monthly_stats:
                monthly_stats[beep_month] = []
            monthly_stats[beep_month].append(beep)

        months = []
        total_year_minutes = 0
        for month, month_beeps in sorted(monthly_stats.items()):
            month_minutes = len(month_beeps)
            month_hours = month_minutes / 60
            total_year_minutes += month_minutes
            months.append({
                'month': month,
                'hours': round(month_hours, 2),
                'minutes': month_minutes,
                'beep_count': len(month_beeps)
            })

        return jsonify({
            'user': username,
            'period': period,
            'year': start_date.strftime('%Y'),
            'total_hours': round(total_year_minutes / 60, 2),
            'total_minutes': total_year_minutes,
            'months': months
        })

@app.route('/beeps/<username>', methods=['DELETE'])
def delete_beeps(username):
    """Delete beeps in a specific time range (operates in UTC)"""
    start_datetime_str = request.args.get('start_datetime')
    end_datetime_str = request.args.get('end_datetime')

    if not start_datetime_str or not end_datetime_str:
        return jsonify({'error': 'start_datetime and end_datetime are required (ISO 8601 format)'}), 400

    try:
        # Parse UTC datetime strings (expected format: 2026-05-07T06:11:00.000Z)
        start_datetime_utc = datetime.fromisoformat(start_datetime_str.replace('Z', '+00:00'))
        end_datetime_utc = datetime.fromisoformat(end_datetime_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use ISO 8601 format with timezone'}), 400

    if start_datetime_utc >= end_datetime_utc:
        return jsonify({'error': 'start_datetime must be before end_datetime'}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Backend operates strictly on UTC
    # Handle both old (local time, no Z) and new (UTC with Z) timestamp formats in DB
    # Convert UTC range back to local for old timestamps
    offset = datetime.now() - datetime.utcnow()
    start_datetime_local = start_datetime_utc + offset
    end_datetime_local = end_datetime_utc + offset

    cursor.execute('''
        DELETE FROM presence_beeps
        WHERE username = ? AND (
            (timestamp >= ? AND timestamp < ?) OR
            (timestamp >= ? AND timestamp < ?)
        )
    ''', (username,
          start_datetime_local.isoformat(), end_datetime_local.isoformat(),
          start_datetime_utc.isoformat() + 'Z', end_datetime_utc.isoformat() + 'Z')
    )

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return jsonify({
        'status': 'success',
        'deleted_count': deleted_count,
        'user': username,
        'start_datetime': start_datetime_str,
        'end_datetime': end_datetime_str
    }), 200

@app.route('/')
def index():
    """Serve the frontend"""
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Presence Tracker API')
    parser.add_argument('--host', default='localhost', help='Host to bind to (default: localhost)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', default=True, help='Enable debug mode (default: True)')
    args = parser.parse_args()

    init_db()
    print("Starting Presence Tracker API...")
    print(f"Beep endpoint: http://{args.host}:{args.port}/beep?user=YOUR_NAME")
    print(f"Web interface: http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=args.debug)
