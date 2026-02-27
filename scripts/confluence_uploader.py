#!/usr/bin/env python3
"""
Meeting Transcript to Confluence Uploader
Monitors a folder for new meeting transcripts and uploads them to Confluence
with AI-generated summaries and action items.
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
import requests

# Configuration
MEETINGS_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = MEETINGS_DIR / ".processed_transcripts.json"
CONFIG_FILE = MEETINGS_DIR / ".confluence_config.json"


class TranscriptProcessor:
    def __init__(self):
        self.load_config()
        self.load_state()

    def load_config(self):
        """Load configuration from file or create default."""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
        else:
            print(f"Error: Config file not found at {CONFIG_FILE}")
            print("   Run setup.sh first to configure your credentials.")
            sys.exit(1)

    def load_state(self):
        """Load processing state."""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = {"processed": []}

    def save_state(self):
        """Save processing state."""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def is_processed(self, filename):
        """Check if file has been processed."""
        return filename in self.state.get("processed", [])

    def mark_processed(self, filename, page_url):
        """Mark file as processed."""
        if "processed" not in self.state:
            self.state["processed"] = []
        self.state["processed"].append({
            "filename": filename,
            "processed_at": datetime.now().isoformat(),
            "page_url": page_url
        })
        self.save_state()

    def extract_date(self, filename, content):
        """Extract meeting date from filename or content."""
        # Try filename first (e.g., "2024-01-26-meeting.txt")
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return match.group(1)

        # Try content
        match = re.search(r'(\d{4}-\d{2}-\d{2})', content[:500])
        if match:
            return match.group(1)

        # Default to today
        return datetime.now().strftime("%Y-%m-%d")

    def generate_analysis(self, transcript):
        """Generate summary and action items using Claude API."""
        api_key = self.config.get("anthropic_api_key")

        if not api_key:
            print("   Warning: No Anthropic API key configured, using simple extraction")
            return self.simple_analysis(transcript)

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)

            prompt = f"""Analyze this meeting transcript and provide:

1. A concise summary (2-3 sentences)
2. A list of clear action items with owners if mentioned

Format your response EXACTLY as:
SUMMARY:
[your summary here]

ACTION ITEMS:
- [action item 1]
- [action item 2]

Transcript:
{transcript}"""

            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text

        except ImportError:
            print("   Warning: anthropic package not installed. Install with: pip install anthropic")
            return self.simple_analysis(transcript)
        except Exception as e:
            print(f"   Warning: Error calling Claude API: {e}")
            return self.simple_analysis(transcript)

    def simple_analysis(self, transcript):
        """Simple fallback analysis without AI."""
        lines = transcript.split('\n')
        summary = f"Meeting transcript with {len(lines)} lines recorded."

        # Extract lines that look like action items
        action_keywords = ['action', 'todo', 'task', 'follow up', 'next step', 'assign']
        action_items = []
        for line in lines:
            if any(keyword in line.lower() for keyword in action_keywords):
                action_items.append(line.strip())

        if not action_items:
            action_items = ["Review meeting notes"]

        result = f"SUMMARY:\n{summary}\n\nACTION ITEMS:\n"
        result += "\n".join(f"- {item}" for item in action_items[:10])
        return result

    def parse_analysis(self, analysis):
        """Parse analysis into summary and action items."""
        parts = analysis.split("ACTION ITEMS:")

        if len(parts) == 2:
            summary = parts[0].replace("SUMMARY:", "").strip()
            action_items = [line.strip() for line in parts[1].strip().split('\n') if line.strip()]
        else:
            summary = "Meeting notes recorded."
            action_items = ["Review meeting transcript"]

        return summary, action_items

    def create_confluence_page(self, title, summary, action_items, transcript):
        """Create a Confluence page with the meeting content."""
        # Build page body in Confluence storage format
        action_items_html = "\n".join(f"<li>{item.lstrip('- ')}</li>" for item in action_items)

        # Escape HTML in transcript
        transcript_escaped = (transcript
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))

        body_html = f"""
<h2>Summary</h2>
<p>{summary}</p>

<h2>Action Items</h2>
<ul>
{action_items_html}
</ul>

<h2>Full Transcript</h2>
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">Click to expand full transcript</ac:parameter>
  <ac:rich-text-body>
    <pre>{transcript_escaped}</pre>
  </ac:rich-text-body>
</ac:structured-macro>

<p><em>Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
"""

        # Prepare page data
        page_data = {
            "type": "page",
            "title": title,
            "space": {"key": self.config["space_key"]},
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage"
                }
            }
        }

        if self.config.get("parent_page_id"):
            page_data["ancestors"] = [{"id": self.config["parent_page_id"]}]

        # Create page via Confluence API
        url = f"{self.config['confluence_url']}/rest/api/content"
        auth = (self.config["confluence_email"], self.config["confluence_api_token"])

        try:
            response = requests.post(
                url,
                json=page_data,
                auth=auth,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                page_url = f"{self.config['confluence_url']}/spaces/{self.config['space_key']}/pages/{result['id']}"
                print(f"   Created page: {page_url}")
                return page_url
            else:
                print(f"   Error creating page: {response.status_code}")
                print(f"      {response.text}")
                return None

        except Exception as e:
            print(f"   Error: {e}")
            return None

    def process_transcripts(self):
        """Process all new transcript files."""
        print("Scanning for new meeting transcripts...")
        print(f"   Directory: {MEETINGS_DIR}")

        if not self.config.get("confluence_api_token"):
            print(f"\nError: Confluence API token not configured!")
            print(f"   Run setup.sh or edit {CONFIG_FILE}")
            return

        # Find all .txt files
        transcript_files = list(MEETINGS_DIR.glob("*.txt"))
        new_files = [f for f in transcript_files if not self.is_processed(f.name)]

        if not new_files:
            print("   No new transcripts found.")
            return

        print(f"   Found {len(new_files)} new transcript(s)\n")

        for transcript_file in new_files:
            print(f"Processing: {transcript_file.name}")

            # Read content
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"   Error reading file: {e}")
                continue

            if not content.strip():
                print("   Empty file, skipping")
                continue

            # Extract date
            meeting_date = self.extract_date(transcript_file.name, content)

            # Generate analysis
            print("   Generating summary and action items...")
            analysis = self.generate_analysis(content)
            summary, action_items = self.parse_analysis(analysis)

            # Create page title
            page_title = f"Meeting Notes - {meeting_date} - {transcript_file.stem}"

            # Create Confluence page
            print("   Creating Confluence page...")
            page_url = self.create_confluence_page(page_title, summary, action_items, content)

            if page_url:
                self.mark_processed(transcript_file.name, page_url)
                print()
            else:
                print("   Failed to create page, will retry next time\n")

        print("Processing complete!")


def main():
    processor = TranscriptProcessor()
    processor.process_transcripts()


if __name__ == "__main__":
    main()
