#!/bin/bash
# Wrapper script for Mac Automator - Analyze and Upload Meeting Transcripts

# Auto-detect directory from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Log file - stored outside the watched directory to avoid retriggering launchd
LOG_DIR="$HOME/Library/Logs/meeting-summarizer"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/automator.log"

# Redirect all output to log file
exec >> "$LOG_FILE" 2>&1

echo "=== Automator run started at $(date) ==="

cd "$ROOT_DIR"

# Find the right Python - launchd has a minimal PATH so we check common locations
PYTHON_PATH=""
if [ -f "$ROOT_DIR/.python_path" ]; then
    PYTHON_PATH="$(cat "$ROOT_DIR/.python_path")"
fi

if [ -z "$PYTHON_PATH" ] || [ ! -x "$PYTHON_PATH" ]; then
    # Search common locations
    for candidate in \
        "$HOME/.pyenv/shims/python3" \
        "/opt/homebrew/bin/python3" \
        "/usr/local/bin/python3" \
        "/usr/bin/python3"; do
        if [ -x "$candidate" ]; then
            PYTHON_PATH="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON_PATH" ]; then
    echo "Error: python3 not found"
    exit 1
fi

echo "Using Python: $PYTHON_PATH"
"$PYTHON_PATH" "$SCRIPT_DIR/analyze_and_upload.py"

# Display notification when done
if [ $? -eq 0 ]; then
    echo "=== Analysis and upload successful at $(date) ==="
    osascript -e 'display notification "Meeting transcripts analyzed and uploaded to Confluence" with title "Meeting Notes Uploader"' 2>/dev/null
else
    echo "=== Analysis or upload failed at $(date) ==="
    osascript -e 'display notification "Failed - check automator.log" with title "Meeting Notes Uploader"' 2>/dev/null
fi
