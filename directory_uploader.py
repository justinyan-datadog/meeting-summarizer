#!/usr/bin/env python3
"""
Directory-based Meeting Transcript Uploader
Maintains a chronological directory page with child pages for each meeting
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


class DirectoryUploader:
    def __init__(self):
        self.load_config()
        self.load_state()
        self.load_analyses()
        self.meetings = []
        self.directory_page_id = self.config.get("parent_page_id")

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

    def get_processed_meetings(self):
        """Get list of all processed meetings with metadata."""
        meetings = []
        for item in self.state.get("processed", []):
            if isinstance(item, dict):
                meetings.append(item)
        return sorted(meetings, key=lambda x: x.get("meeting_date", ""), reverse=True)

    def mark_processed(self, filename, page_url, page_id, meeting_date, summary_snippet):
        """Mark file as processed with metadata."""
        if "processed" not in self.state:
            self.state["processed"] = []

        self.state["processed"].append({
            "filename": filename,
            "page_id": page_id,
            "page_url": page_url,
            "meeting_date": meeting_date,
            "summary_snippet": summary_snippet,
            "processed_at": datetime.now().isoformat()
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

        # Default to file modification time
        return datetime.fromtimestamp(Path(MEETINGS_DIR / filename).stat().st_mtime).strftime("%Y-%m-%d")

    def upload_attachment(self, page_id, filepath):
        """Upload file as attachment to Confluence page."""
        url = f"{self.config['confluence_url']}/rest/api/content/{page_id}/child/attachment"
        auth = (self.config["confluence_email"], self.config["confluence_api_token"])

        try:
            with open(filepath, 'rb') as f:
                files = {'file': (filepath.name, f, 'text/plain')}
                headers = {'X-Atlassian-Token': 'no-check'}

                response = requests.post(
                    url,
                    files=files,
                    auth=auth,
                    headers=headers
                )

                if response.status_code == 200:
                    result = response.json()
                    return result['results'][0]['_links']['download']
                else:
                    print(f"      Warning: Failed to upload attachment: {response.status_code}")
                    return None

        except Exception as e:
            print(f"      Warning: Error uploading attachment: {e}")
            return None

    def update_page_with_attachment(self, page_id, title, analysis, transcript, download_link, filename):
        """Update page body to include attachment download link."""
        def format_list(items):
            if not items:
                return "<p><em>None</em></p>"
            return "<ul>\n" + "\n".join(f"<li>{item.lstrip('- ')}</li>" for item in items) + "\n</ul>"

        transcript_escaped = (transcript
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))

        body_html = f"""
<h2>Key Decisions</h2>
{format_list(analysis.get('key_decisions', []))}

<h2>Discussion Points</h2>
{format_list(analysis.get('discussion_points', []))}

<h2>Action Items</h2>
{format_list(analysis.get('action_items', []))}

<h2>Open Questions</h2>
{format_list(analysis.get('open_questions', []))}

<h2>Attachments</h2>
<p><a href="{self.config['confluence_url']}{download_link}">Download Raw Transcript: {filename}</a></p>

<h2>Full Transcript</h2>
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">Click to expand full transcript</ac:parameter>
  <ac:rich-text-body>
    <pre>{transcript_escaped}</pre>
  </ac:rich-text-body>
</ac:structured-macro>

<p><em>Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
"""

        # Get current page version
        url = f"{self.config['confluence_url']}/rest/api/content/{page_id}"
        auth = (self.config["confluence_email"], self.config["confluence_api_token"])

        try:
            response = requests.get(url, auth=auth)
            if response.status_code == 200:
                current = response.json()
                current_version = current['version']['number']

                # Update page
                update_data = {
                    "id": page_id,
                    "type": "page",
                    "title": title,
                    "space": {"key": self.config["space_key"]},
                    "ancestors": [{"id": self.directory_page_id}],
                    "body": {
                        "storage": {
                            "value": body_html,
                            "representation": "storage"
                        }
                    },
                    "version": {"number": current_version + 1}
                }

                response = requests.put(
                    url,
                    json=update_data,
                    auth=auth,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    return True
                else:
                    print(f"      Warning: Failed to update page with attachment link: {response.status_code}")
                    return False

        except Exception as e:
            print(f"      Warning: Error updating page: {e}")
            return False

    def create_confluence_page(self, title, analysis, transcript, meeting_date):
        """Create a Confluence page as a child of the directory."""
        def format_list(items):
            if not items:
                return "<p><em>None</em></p>"
            return "<ul>\n" + "\n".join(f"<li>{item.lstrip('- ')}</li>" for item in items) + "\n</ul>"

        transcript_escaped = (transcript
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))

        body_html = f"""
<h2>Key Decisions</h2>
{format_list(analysis.get('key_decisions', []))}

<h2>Discussion Points</h2>
{format_list(analysis.get('discussion_points', []))}

<h2>Action Items</h2>
{format_list(analysis.get('action_items', []))}

<h2>Open Questions</h2>
{format_list(analysis.get('open_questions', []))}

<h2>Attachments</h2>
<p><strong>Raw Transcript File</strong> (will be attached after page creation)</p>

<h2>Full Transcript</h2>
<ac:structured-macro ac:name="expand" ac:schema-version="1">
  <ac:parameter ac:name="title">Click to expand full transcript</ac:parameter>
  <ac:rich-text-body>
    <pre>{transcript_escaped}</pre>
  </ac:rich-text-body>
</ac:structured-macro>

<p><em>Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
"""

        page_data = {
            "type": "page",
            "title": title,
            "space": {"key": self.config["space_key"]},
            "ancestors": [{"id": self.directory_page_id}],
            "body": {
                "storage": {
                    "value": body_html,
                    "representation": "storage"
                }
            }
        }

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
                return page_url, page_id
            else:
                print(f"   Error creating page: {response.status_code}")
                print(f"      {response.text[:200]}")
                return None, None

        except Exception as e:
            print(f"   Error: {e}")
            return None, None

    def update_directory_page(self):
        """Update the directory page with all meetings."""
        if not self.directory_page_id:
            print("   Warning: No parent_page_id configured, skipping directory update")
            return False

        meetings = self.get_processed_meetings()

        if not meetings:
            print("   No meetings to add to directory")
            return

        # Build table rows
        rows = []
        for meeting in meetings:
            page_id = meeting.get("page_id")
            title = meeting.get("filename", "").replace(".txt", "")
            summary_snippet = meeting.get("summary_snippet", "Meeting notes")[:100]
            date = meeting.get("meeting_date", "")

            row = f"""<tr>
<td>{date}</td>
<td><ac:link><ri:page ri:content-title="Meeting Notes - {date} - {title.replace(':', ' ')}" /></ac:link></td>
<td>{summary_snippet}</td>
</tr>"""
            rows.append(row)

        body_html = f"""<h2>Meeting Notes</h2>
<p>Automatically generated meeting transcripts with AI-powered summaries and action items.</p>

<h3>Recent Meetings</h3>
<table>
<colgroup>
<col style="width: 150px;" />
<col style="width: 400px;" />
<col style="width: 200px;" />
</colgroup>
<thead>
<tr>
<th>Date</th>
<th>Meeting</th>
<th>Summary</th>
</tr>
</thead>
<tbody>
{"".join(rows)}
</tbody>
</table>

<p><em>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>"""

        # Get current version
        url = f"{self.config['confluence_url']}/rest/api/content/{self.directory_page_id}"
        auth = (self.config["confluence_email"], self.config["confluence_api_token"])

        try:
            response = requests.get(url, auth=auth)
            if response.status_code == 200:
                current = response.json()
                current_version = current['version']['number']

                # Update page
                update_data = {
                    "id": self.directory_page_id,
                    "type": "page",
                    "title": "Meeting Notes Directory",
                    "space": {"key": self.config["space_key"]},
                    "body": {
                        "storage": {
                            "value": body_html,
                            "representation": "storage"
                        }
                    },
                    "version": {"number": current_version + 1}
                }

                update_url = f"{self.config['confluence_url']}/rest/api/content/{self.directory_page_id}"
                response = requests.put(
                    update_url,
                    json=update_data,
                    auth=auth,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    print(f"   Updated directory page")
                    return True
                else:
                    print(f"   Warning: Failed to update directory: {response.status_code}")
                    return False

        except Exception as e:
            print(f"   Error updating directory: {e}")
            return False

    def process_transcripts(self):
        """Process all new transcripts and update directory."""
        print("Meeting Notes Directory Uploader\n")

        if not self.config.get("confluence_api_token"):
            print("Error: Confluence API token not configured!")
            print("   Run setup.sh to configure your credentials.")
            return

        if not self.analyses:
            print("Warning: No analyses found! Please run the analysis step first.")
            return

        new_count = 0
        for filename, analysis in self.analyses.items():
            filepath = MEETINGS_DIR / filename

            if not filepath.exists():
                print(f"Warning: File not found: {filename}")
                continue

            if self.is_processed(filename):
                print(f"Already processed: {filename}")
                continue

            print(f"Processing: {filename}")

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"   Error reading file: {e}")
                continue

            if not content.strip():
                print("   Empty file, skipping")
                continue

            meeting_date = self.extract_date(filename, content)

            # Create summary snippet from key decisions or discussion points
            summary_snippet = ""
            if analysis.get('key_decisions'):
                summary_snippet = analysis['key_decisions'][0][:100]
            elif analysis.get('discussion_points'):
                summary_snippet = analysis['discussion_points'][0][:100]
            elif analysis.get('action_items'):
                summary_snippet = analysis['action_items'][0][:100]
            else:
                summary_snippet = "Meeting notes"

            if len(summary_snippet) > 100:
                summary_snippet = summary_snippet[:100] + "..."

            # Create page title
            page_title = f"Meeting Notes - {meeting_date} - {filepath.stem}"

            print("   Creating Confluence page...")
            page_url, page_id = self.create_confluence_page(
                page_title, analysis, content, meeting_date
            )

            if page_url and page_id:
                # Upload raw transcript file as attachment
                print("   Attaching raw transcript file...")
                download_link = self.upload_attachment(page_id, filepath)

                if download_link:
                    # Update page with download link
                    self.update_page_with_attachment(page_id, page_title, analysis, content, download_link, filepath.name)
                    print(f"   Attached: {filepath.name}")

                self.mark_processed(filename, page_url, page_id, meeting_date, summary_snippet)
                print(f"   Created: {page_url}\n")
                new_count += 1
            else:
                print("   Failed to create page\n")

        if new_count > 0:
            print("Updating directory page...")
            self.update_directory_page()

        confluence_url = self.config.get('confluence_url', '')
        space_key = self.config.get('space_key', '')
        print(f"\nProcessed {new_count} new transcript(s)!")
        if self.directory_page_id:
            print(f"Directory: {confluence_url}/spaces/{space_key}/pages/{self.directory_page_id}")


def main():
    uploader = DirectoryUploader()
    uploader.process_transcripts()


if __name__ == "__main__":
    main()
