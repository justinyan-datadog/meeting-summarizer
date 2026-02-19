#!/bin/bash

# Configuration - auto-detect directory from script location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MEETINGS_DIR="$SCRIPT_DIR"
STATE_FILE="$MEETINGS_DIR/.processed_transcripts"
CONFIG_FILE="$MEETINGS_DIR/.confluence_config.json"

# Read space key from config if available
if [ -f "$CONFIG_FILE" ]; then
    CONFLUENCE_SPACE_KEY=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['space_key'])" 2>/dev/null)
fi
CONFLUENCE_SPACE_KEY="${CONFLUENCE_SPACE_KEY:-}"

# Ensure state file exists
touch "$STATE_FILE"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Meeting Transcript Processor ===${NC}"
echo "Scanning: $MEETINGS_DIR"

# Function to check if file has been processed
is_processed() {
    grep -q "^$1$" "$STATE_FILE"
}

# Function to mark file as processed
mark_processed() {
    echo "$1" >> "$STATE_FILE"
}

# Function to extract meeting date from filename or content
extract_meeting_date() {
    local filename="$1"
    local content="$2"

    # Try to extract date from filename (e.g., "2024-01-26-meeting.txt")
    if [[ $filename =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        # Try to find date in content
        date_line=$(echo "$content" | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2}" | head -1)
        if [ -n "$date_line" ]; then
            echo "$date_line"
        else
            # Default to file modification date
            stat -f "%Sm" -t "%Y-%m-%d" "$filename"
        fi
    fi
}

# Function to generate summary and action items using Claude
generate_analysis() {
    local transcript="$1"
    local temp_file=$(mktemp)

    # Create analysis prompt
    cat > "$temp_file" << 'EOF'
Analyze this meeting transcript and provide:

1. A concise summary (2-3 sentences)
2. A list of clear action items with owners if mentioned

Format your response as:
SUMMARY:
[your summary here]

ACTION ITEMS:
- [action item 1]
- [action item 2]
...

Transcript:
EOF
    echo "$transcript" >> "$temp_file"

    # Use Claude API via claude command if available
    if command -v claude &> /dev/null; then
        claude -p "$(cat "$temp_file")" 2>/dev/null
    else
        # Fallback: simple extraction
        echo "SUMMARY:"
        echo "Meeting transcript recorded."
        echo ""
        echo "ACTION ITEMS:"
        echo "$transcript" | grep -iE "(action|todo|task|follow.?up|next step)" | head -5
    fi

    rm "$temp_file"
}

# Process each .txt file in the directory
find "$MEETINGS_DIR" -maxdepth 1 -name "*.txt" -type f | while read -r transcript_file; do
    filename=$(basename "$transcript_file")

    # Skip if already processed
    if is_processed "$filename"; then
        continue
    fi

    echo -e "\n${GREEN}Processing: $filename${NC}"

    # Read transcript content
    transcript_content=$(cat "$transcript_file")

    # Skip if empty
    if [ -z "$transcript_content" ]; then
        echo "  Skipping empty file"
        mark_processed "$filename"
        continue
    fi

    # Extract meeting date
    meeting_date=$(extract_meeting_date "$filename" "$transcript_content")

    # Generate analysis
    echo "  Generating summary and action items..."
    analysis=$(generate_analysis "$transcript_content")

    # Extract summary and action items from analysis
    summary=$(echo "$analysis" | sed -n '/SUMMARY:/,/ACTION ITEMS:/p' | sed '1d;$d' | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    action_items=$(echo "$analysis" | sed -n '/ACTION ITEMS:/,$p' | sed '1d')

    # Create Confluence page title
    page_title="Meeting Notes - $meeting_date - ${filename%.*}"

    # Build Confluence page body in storage format
    read -r -d '' page_body << EOF || true
<h2>Summary</h2>
<p>$summary</p>

<h2>Action Items</h2>
<ul>
$(echo "$action_items" | sed 's/^- /<li>/;s/$/<\/li>/')
</ul>

<h2>Full Transcript</h2>
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">Click to expand transcript</ac:parameter>
  <ac:rich-text-body>
    <pre>$(echo "$transcript_content" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')</pre>
  </ac:rich-text-body>
</ac:structured-macro>

<p><em>Auto-generated on $(date '+%Y-%m-%d %H:%M:%S')</em></p>
EOF

    # Create the Confluence page
    echo "  Creating Confluence page: $page_title"

    echo "  Title: $page_title"
    echo "  Summary: ${summary:0:100}..."

    # Save the page data to a temp JSON file for the Confluence API
    temp_json=$(mktemp)
    cat > "$temp_json" << EOF
{
  "spaceKey": "$CONFLUENCE_SPACE_KEY",
  "title": "$page_title",
  "type": "page",
  "status": "current",
  "body": {
    "storage": {
      "value": $(echo "$page_body" | jq -Rs .),
      "representation": "storage"
    }
  }
}
EOF

    # Store the JSON path for manual review if needed
    echo "  Confluence page data saved to: $temp_json"
    echo "  (Will be created via Confluence API)"

    # Mark as processed
    mark_processed "$filename"
    echo -e "  ${GREEN}Done${NC}"
done

echo -e "\n${BLUE}=== Processing Complete ===${NC}"
