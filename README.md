# Meeting Transcript Summarizer

Automatically summarizes meeting transcripts using Claude and uploads them to Confluence with structured notes, action items, and the full transcript.

## Quick Start

```bash
git clone https://github.com/justinyan-datadog/meeting-summarizer.git meeting-summarizer-tool
cd meeting-summarizer-tool
./setup.sh
```

The setup script will:
- Install Python dependencies (`requests`, `anthropic`)
- Prompt for your Confluence and Anthropic API credentials
- Optionally install a macOS launchd agent for automatic processing

## How It Works

1. Drop a `.txt` meeting transcript file into this folder
2. The automation detects the new file and:
   - Sends the transcript to Claude for analysis
   - Extracts key decisions, discussion points, action items, and open questions
   - Creates a Confluence page with the structured summary
   - Attaches the raw transcript file
   - Updates a directory page linking all meetings

## Files

| Script | Purpose |
|---|---|
| `setup.sh` | One-time setup: credentials, dependencies, scheduling |
| `run_uploader.sh` | Entry point wrapper (called by launchd or manually) |
| `analyze_and_upload.py` | Main pipeline: analyze with Claude then upload |
| `directory_uploader.py` | Creates/updates Confluence pages with directory |
| `confluence_uploader.py` | Standalone Confluence uploader with built-in analysis |
| `smart_uploader.py` | Uploads using pre-generated analyses |
| `process_with_claude.py` | Prepares transcripts for batch analysis |
| `process_transcripts.sh` | Shell-based transcript processor |

## Requirements

- Python 3.8+
- macOS (for launchd automation; scripts work on Linux without the agent)
- A Confluence instance with API access
- An Anthropic API key

## Manual Usage

```bash
cd ~/meeting-summarizer-tool
./run_uploader.sh

# Or run the Python script directly
python3 analyze_and_upload.py
```

## Configuration

All settings are stored in `.confluence_config.json` (created by `setup.sh`):

```json
{
  "confluence_url": "https://datadoghq.atlassian.net/wiki",
  "confluence_email": "first.last@datadoghq.com",
  "confluence_api_token": "<your-token>",
  "space_key": "<extracted-from-url>",
  "parent_page_id": "<extracted-from-url>",
  "anthropic_api_key": "<your-key>"
}
```

The `space_key` and `parent_page_id` are automatically extracted from the Confluence page URL you provide during setup.

## Transcript File Format

For best results, include a date in the filename:
- `2026-01-26 Team Standup.txt`
- `1-26-2026 Project Sync.txt`

The script will also try to extract dates from the file content.

## Uninstall the Launchd Agent

```bash
launchctl bootout "gui/$(id -u)/com.meetings.uploader"
rm ~/Library/LaunchAgents/com.meetings.uploader.plist
```
