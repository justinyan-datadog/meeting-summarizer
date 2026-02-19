#!/bin/bash
#
# Meeting Summarizer - Setup Script
#
# Run this once to configure the automation for your machine.
# It will prompt for your credentials and optionally install
# a launchd agent to run automatically.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.confluence_config.json"
PLIST_NAME="com.meetings.uploader"

echo "========================================"
echo "  Meeting Summarizer - Setup"
echo "========================================"
echo ""
echo "This script will configure the meeting transcript"
echo "summarizer for your machine."
echo ""
echo "Scripts directory: $SCRIPT_DIR"
echo ""

# -----------------------------------------------
# 1. Check Python and install dependencies
# -----------------------------------------------
echo "--- Step 1: Python dependencies ---"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3 first."
    exit 1
fi

PYTHON_FULL_PATH="$(which python3)"
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Found: $PYTHON_VERSION ($PYTHON_FULL_PATH)"

echo "Installing required packages..."
python3 -m pip install --quiet requests anthropic
echo "Done."

# Save Python path so launchd/Automator can find the right one
echo "$PYTHON_FULL_PATH" > "$SCRIPT_DIR/.python_path"
echo "Saved Python path for automation: $PYTHON_FULL_PATH"
echo ""

# -----------------------------------------------
# 2. Gather Confluence credentials
# -----------------------------------------------
echo "--- Step 2: Confluence configuration ---"
echo ""

if [ -f "$CONFIG_FILE" ]; then
    echo "Existing config found at: $CONFIG_FILE"
    read -p "Overwrite it? (y/N): " overwrite
    if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
        echo "Keeping existing config."
        SKIP_CONFIG=true
    fi
fi

if [ "${SKIP_CONFIG:-}" != "true" ]; then
    CONFLUENCE_URL="https://datadoghq.atlassian.net/wiki"
    echo "Confluence URL: $CONFLUENCE_URL"
    echo ""

    read -p "Your Datadog email (e.g. first.last@datadoghq.com): " CONFLUENCE_EMAIL

    echo ""
    echo "You need a Confluence API token."
    echo "Create one at: https://id.atlassian.com/manage-profile/security/api-tokens"
    read -sp "Confluence API token: " CONFLUENCE_TOKEN
    echo ""

    echo ""
    echo "Your space key and parent page ID can be found in any Confluence page URL:"
    echo ""
    echo "  https://datadoghq.atlassian.net/wiki/spaces/SPACE_KEY/pages/PAGE_ID/Page-Title"
    echo "                                               ^^^^^^^^^       ^^^^^^^"
    echo ""
    echo "Example:"
    echo "  https://datadoghq.atlassian.net/wiki/spaces/~7120202f.../pages/6257442955/Meeting-Summarizer"
    echo "  Space key: ~7120202f..."
    echo "  Page ID:   6257442955"
    echo ""
    echo "For personal spaces, the space key starts with ~ followed by a long ID."
    echo "For team spaces, it's a short code like TEAM or ENG."
    echo ""
    read -p "Confluence space key: " SPACE_KEY

    echo ""
    echo "The parent page ID is the number after /pages/ in the URL."
    echo "Meeting notes will be created as children of this page."
    read -p "Parent page ID: " PARENT_PAGE_ID

    echo ""
    echo "--- Step 3: Anthropic API key ---"
    echo ""
    echo "The summarizer uses Claude to analyze transcripts."
    echo "Get an API key at: https://console.anthropic.com/settings/keys"
    read -sp "Anthropic API key: " ANTHROPIC_KEY
    echo ""

    # Build config JSON
    if [ -z "$PARENT_PAGE_ID" ]; then
        PARENT_PAGE_JSON="null"
    else
        PARENT_PAGE_JSON="\"$PARENT_PAGE_ID\""
    fi

    cat > "$CONFIG_FILE" << EOF
{
  "confluence_url": "$CONFLUENCE_URL",
  "confluence_email": "$CONFLUENCE_EMAIL",
  "confluence_api_token": "$CONFLUENCE_TOKEN",
  "space_key": "$SPACE_KEY",
  "parent_page_id": $PARENT_PAGE_JSON,
  "anthropic_api_key": "$ANTHROPIC_KEY"
}
EOF

    chmod 600 "$CONFIG_FILE"
    echo ""
    echo "Config saved to: $CONFIG_FILE"
    echo "(Permissions set to owner-only read/write)"
fi

echo ""

# -----------------------------------------------
# 4. Make scripts executable
# -----------------------------------------------
echo "--- Step 4: File permissions ---"
chmod +x "$SCRIPT_DIR/run_uploader.sh"
chmod +x "$SCRIPT_DIR/analyze_and_upload.py"
chmod +x "$SCRIPT_DIR/confluence_uploader.py"
chmod +x "$SCRIPT_DIR/process_transcripts.sh"
echo "Scripts marked as executable."
echo ""

# -----------------------------------------------
# 5. Optional: install launchd agent
# -----------------------------------------------
echo "--- Step 5: Automatic scheduling (optional) ---"
echo ""
echo "You can install a macOS launchd agent that automatically"
echo "processes new .txt files whenever they appear in:"
echo "  $SCRIPT_DIR"
echo ""
read -p "Install the launchd agent? (y/N): " INSTALL_AGENT

if [[ "$INSTALL_AGENT" =~ ^[Yy]$ ]]; then
    PLIST_DIR="$HOME/Library/LaunchAgents"
    PLIST_FILE="$PLIST_DIR/$PLIST_NAME.plist"

    LOG_DIR="$HOME/Library/Logs/meeting-summarizer"
    mkdir -p "$PLIST_DIR" "$LOG_DIR"

    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$SCRIPT_DIR/run_uploader.sh</string>
    </array>

    <key>WatchPaths</key>
    <array>
        <string>$SCRIPT_DIR</string>
    </array>

    <key>StandardOutPath</key>
    <string>$LOG_DIR/uploader.log</string>

    <key>StandardErrorPath</key>
    <string>$LOG_DIR/uploader.error.log</string>
</dict>
</plist>
EOF

    # Unload first if already loaded (ignore errors)
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || true

    launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"
    echo "Launchd agent installed and loaded."
    echo "  Plist: $PLIST_FILE"
    echo "  It will trigger whenever files change in: $SCRIPT_DIR"
else
    echo "Skipped. You can always run manually:"
    echo "  cd $SCRIPT_DIR && ./run_uploader.sh"
fi

echo ""

# -----------------------------------------------
# 6. Test
# -----------------------------------------------
echo "--- Step 6: Verification ---"
echo ""
echo "Testing config file..."

python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
required = ['confluence_url', 'confluence_email', 'confluence_api_token', 'anthropic_api_key']
missing = [k for k in required if not cfg.get(k)]
if missing:
    print('Warning: Missing values for: ' + ', '.join(missing))
    print('Edit $CONFIG_FILE to add them.')
else:
    print('Config looks good - all required fields are set.')
"

echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "To process transcripts:"
echo "  1. Drop .txt transcript files into: $SCRIPT_DIR"
if [[ "$INSTALL_AGENT" =~ ^[Yy]$ ]]; then
    echo "  2. They will be processed automatically."
else
    echo "  2. Run: cd $SCRIPT_DIR && ./run_uploader.sh"
fi
echo ""
echo "Logs: ~/Library/Logs/meeting-summarizer/automator.log"
echo ""
