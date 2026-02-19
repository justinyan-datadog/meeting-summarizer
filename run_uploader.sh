#!/bin/bash
# Wrapper script for Mac Automator - Analyze and Upload Meeting Transcripts

# Auto-detect directory from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Log file for debugging
LOG_FILE="$SCRIPT_DIR/automator.log"

# Redirect all output to log file
exec >> "$LOG_FILE" 2>&1

echo "=== Automator run started at $(date) ==="

cd "$SCRIPT_DIR"

# Use python3 from PATH (setup.sh ensures dependencies are installed)
python3 analyze_and_upload.py

# Display notification when done
if [ $? -eq 0 ]; then
    echo "=== Analysis and upload successful at $(date) ==="
    osascript -e 'display notification "Meeting transcripts analyzed and uploaded to Confluence" with title "Meeting Notes Uploader"' 2>/dev/null
else
    echo "=== Analysis or upload failed at $(date) ==="
    osascript -e 'display notification "Failed - check automator.log" with title "Meeting Notes Uploader"' 2>/dev/null
fi
