#!/usr/bin/env python3
"""
Smart Meeting Transcript Uploader
Uploads transcripts to Confluence with pre-analyzed summaries
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
import requests

MEETINGS_DIR = Path(__file__).resolve().parent
STATE_FILE = MEETINGS_DIR / ".processed_transcripts.json"
CONFIG_FILE = MEETINGS_DIR / ".confluence_config.json"
ANALYSES_FILE = MEETINGS_DIR / ".transcript_analyses.json"


class SmartUploader:
    def __init__(self):
        self.load_config()
        self.load_state()
        self.load_analyses()

    def load_config(self):
        """Load configuration from file."""
        if not CONFIG_FILE.exists():
            print(f"Error: Config file not found at {CONFIG_FILE}")
            print("   Run setup.sh first to configure your credentials.")
            sys.exit(1)
        with open(CONFIG_FILE, 'r') as f:
            self.config = json.load(f)

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

    def load_analyses(self):
        """Load pre-generated analyses."""
        if ANALYSES_FILE.exists():
            with open(ANALYSES_FILE, 'r') as f:
                self.analyses = json.load(f)
        else:
            self.analyses = {}

    def save_analyses(self):
        """Save analyses to file."""
        with open(ANALYSES_FILE, 'w') as f:
            json.dump(self.analyses, f, indent=2)

    def is_processed(self, filename):
        """Check if file has been processed."""
        processed = self.state.get("processed", [])
        for item in processed:
            if isinstance(item, dict):
                if item.get("filename") == filename:
                    return True
            elif item == filename:
                return True
        return False

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
        # Try filename first
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return match.group(1)

        # Try content
        match = re.search(r'(\d{4}-\d{2}-\d{2})', content[:500])
        if match:
            return match.group(1)

        # Default to today
        return datetime.now().strftime("%Y-%m-%d")

    def get_analysis(self, filename):
        """Get pre-generated analysis for a transcript."""
        return self.analyses.get(filename)

    def create_confluence_page(self, title, summary, action_items, transcript):
        """Create a Confluence page with the meeting content."""
        # Build action items HTML
        action_items_html = "\n".join(
            f"<li>{item.lstrip('- ')}</li>" for item in action_items
        )

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
                page_id = result['id']
                page_url = f"{self.config['confluence_url']}/spaces/{self.config['space_key']}/pages/{page_id}"
                return page_url
            else:
                print(f"   Error creating page: {response.status_code}")
                print(f"      {response.text[:200]}")
                return None

        except Exception as e:
            print(f"   Error: {e}")
            return None

    def process_transcript(self, transcript_file, summary, action_items):
        """Process a single transcript with provided analysis."""
        print(f"Processing: {transcript_file.name}")

        # Read content
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"   Error reading file: {e}")
            return False

        if not content.strip():
            print("   Empty file, skipping")
            return False

        # Extract date
        meeting_date = self.extract_date(transcript_file.name, content)

        # Create page title
        page_title = f"Meeting Notes - {meeting_date} - {transcript_file.stem}"

        # Create Confluence page
        print("   Creating Confluence page...")
        page_url = self.create_confluence_page(page_title, summary, action_items, content)

        if page_url:
            self.mark_processed(transcript_file.name, page_url)
            print(f"   Created: {page_url}\n")
            return True
        else:
            print("   Failed to create page\n")
            return False

    def upload_all(self):
        """Upload all transcripts with pre-generated analyses."""
        print("Smart Meeting Transcript Uploader\n")

        if not self.config.get("confluence_api_token"):
            print("Error: Confluence API token not configured!")
            print("   Run setup.sh to configure your credentials.")
            return

        if not self.analyses:
            print("Warning: No analyses found! Please run the analysis step first.")
            print("   Analyses should be in: .transcript_analyses.json")
            return

        success_count = 0
        for filename, analysis in self.analyses.items():
            filepath = MEETINGS_DIR / filename

            if not filepath.exists():
                print(f"Warning: File not found: {filename}")
                continue

            if self.is_processed(filename):
                print(f"Already processed: {filename}")
                continue

            if self.process_transcript(
                filepath,
                analysis['summary'],
                analysis['action_items']
            ):
                success_count += 1

        print(f"\nUploaded {success_count} transcript(s) to Confluence!")


def main():
    uploader = SmartUploader()
    uploader.upload_all()


if __name__ == "__main__":
    main()
