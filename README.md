# Presence Tracker

A simple Python REST backend for tracking user presence with a web frontend for visualizing work hours.

## Features

- REST API endpoint for recording presence "beeps"
- Time calculation based on beep count (1 beep = 1 minute)
- Automatic session calculation (beeps within 2 minutes are grouped into work sessions)
- SQLite database for persistence
- Web interface with:
  - **Daily view**: Interactive timeline chart showing work sessions throughout the day
  - **Monthly view**: Table showing total hours worked per day with beep counts (days are clickable)
  - **Yearly view**: Table showing total hours worked per month (months are clickable)
- **Remove accidental beeps**: Delete beeps from a specific time range (useful when computer was left on accidentally)
- Support for multiple users
- Browser history support (back/forward buttons work)

## Installation

1. Install dependencies using uv:
```bash
uv sync
```

2. Run the server:
```bash
uv run python app.py
```

The server will start on `http://localhost:5000`

You can customize the host and port:
```bash
uv run python app.py --host 0.0.0.0 --port 8001
```

Available options:
- `--host`: Host to bind to (default: localhost)
- `--port`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode (default: True)

### Alternative: Using pip

If you prefer pip:
```bash
pip install -r requirements.txt
python app.py
```

## Usage

### Recording Presence (Client Side)

Send a beep from your computer using curl:

```bash
# Simple GET request (replace YourName with your username)
curl "http://localhost:5000/beep?user=YourName"

# Or POST request with JSON
curl -X POST http://localhost:5000/beep \
  -H "Content-Type: application/json" \
  -d '{"user":"YourName"}'
```

### Automating Beeps

#### Linux/Mac (using cron):

1. Edit your crontab:
```bash
crontab -e
```

2. Add this line (replace `YourName` with your username and adjust port if needed):
```bash
* * * * * curl -s "http://localhost:5000/beep?user=YourName" > /dev/null 2>&1
```

**If using port 8001:**
```bash
* * * * * curl -s "http://localhost:8001/beep?user=YourName" > /dev/null 2>&1
```

**Explanation:**
- `* * * * *` = Run every minute
- `curl -s` = Silent mode (no progress bar)
- `user=YourName` = Replace YourName with your actual username
- `> /dev/null 2>&1` = Discard output to avoid cron emails

**To verify it's working:**
1. Add the cron job
2. Wait a minute or two
3. Check the web interface to see recorded beeps

#### Linux (using systemd timer):

Create `/etc/systemd/system/presence-beep.service` (replace YourName and adjust port if needed):
```ini
[Unit]
Description=Presence Tracker Beep

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -s "http://localhost:5000/beep?user=YourName"
```

Create `/etc/systemd/system/presence-beep.timer`:
```ini
[Unit]
Description=Send presence beep every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable presence-beep.timer
sudo systemctl start presence-beep.timer
```

#### Windows (using Task Scheduler):

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "Daily" and repeat every 1 minute
4. Action: Start a program
5. Program: `curl`
6. Arguments: `"http://localhost:5000/beep?user=YourName"` (replace YourName and adjust port if needed)

### Viewing Statistics

Open your browser and go to:
```
http://localhost:5000/
```

The web interface allows you to:
- Select a user from the dropdown
- Choose between daily, monthly, or yearly view
- Pick a specific date, month, or year

**Daily View:**
- Visual timeline chart showing when you were active throughout the 24-hour period
- Total hours calculated from beep count (1 beep = 1 minute)
- Session information (first/last activity times)
- Number of work sessions and total beeps
- **Remove accidental beeps**: Form to delete beeps in a specific time range
  - Enter start and end times (e.g., 18:00 to 23:00)
  - Confirmation dialog before deletion
  - Useful for removing beeps when computer was left on accidentally

**Monthly View:**
- Table showing each day of the month
- Total hours worked per day
- Beep count for each day
- Day of week for easy reference
- Monthly total at the top
- Click on any day to view detailed daily timeline

**Yearly View:**
- Table showing each month of the year
- Total hours worked per month
- Beep count for each month
- Yearly total at the top
- Click on any month to view monthly breakdown

## API Endpoints

### POST/GET `/beep`
Record a presence beep

**Parameters:**
- `user` (required): The user's name

**Example:**
```bash
curl "http://localhost:5000/beep?user=john"
```

### GET `/users`
Get list of all users

**Response:**
```json
{
  "users": ["john", "jane"]
}
```

### GET `/stats/<username>`
Get work statistics for a user

**Query Parameters:**
- `period`: "day", "month", or "year" (default: "day")
- `date`: Date in YYYY-MM-DD format (day), YYYY-MM format (month), or YYYY format (year)

**Example (daily stats):**
```bash
curl "http://localhost:5000/stats/john?period=day&date=2026-05-07"
```

**Example (monthly stats):**
```bash
curl "http://localhost:5000/stats/john?period=month&date=2026-05"
```

**Example (yearly stats):**
```bash
curl "http://localhost:5000/stats/john?period=year&date=2026"
```

### DELETE `/beeps/<username>`
Delete beeps in a specific time range

**Query Parameters:**
- `date`: Date in YYYY-MM-DD format
- `start_time`: Start time in HH:MM format (24-hour)
- `end_time`: End time in HH:MM format (24-hour)

**Example:**
```bash
curl -X DELETE "http://localhost:5000/beeps/john?date=2026-05-07&start_time=18:00&end_time=23:00"
```

**Response:**
```json
{
  "status": "success",
  "deleted_count": 300,
  "user": "john",
  "date": "2026-05-07",
  "start_time": "18:00",
  "end_time": "23:00"
}
```

## How It Works

1. Every minute, your computer sends a "beep" to the server with your username
2. The server records the timestamp in an SQLite database
3. Total time is calculated based on the number of beeps (1 beep = 1 minute of work)
4. Sessions are calculated by grouping beeps that are within 2 minutes of each other
5. The web interface displays:
   - **Daily view**: Timeline chart showing activity periods throughout the day
   - **Monthly view**: Table showing total time worked per day
   - **Yearly view**: Table showing total time worked per month

## Database

The application uses SQLite with a single table:

```sql
CREATE TABLE presence_beeps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Database file: `presence.db` (created automatically)

## Configuration

You can modify these settings in `app.py`:

- `DB_PATH`: Database file location
- `app.run()` parameters: Host, port, debug mode
- Session gap threshold (currently 120 seconds) in the `calculate_sessions()` function

## Security Notes

This is a simple local tracking system. For production use, consider:
- Adding authentication
- Using HTTPS
- Implementing rate limiting
- Adding input validation and sanitization
- Running behind a reverse proxy (nginx, Apache)
