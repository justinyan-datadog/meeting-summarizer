# Meeting Transcript Summarizer

Automatically summarizes meeting transcripts using Claude and uploads them to Confluence with structured notes, action items, and the full transcript.

## Quick Start

```bash
git clone https://github.com/justinyan-datadog/meeting-summarizer.git meeting-summarizer-tool
cd meeting-summarizer-tool
./scripts/setup.sh
```

The setup script will:
- Install Python dependencies (`requests`, `anthropic`)
- Prompt for your Confluence and Anthropic API credentials
- Optionally install a macOS launchd agent for automatic processing

## How It Works

1. Drop a `.txt` meeting transcript file into the root folder
2. The automation detects the new file and:
   - Sends the transcript to Claude for analysis
   - Extracts key decisions, discussion points, action items, and open questions
   - Saves a local markdown summary to the `summaries/` folder
   - Creates a Confluence page with the structured summary
   - Attaches the raw transcript file
   - Updates a directory page linking all meetings

## Folder Structure

```
meeting-summarizer-tool/
├── your-meeting.txt        ← drop transcript files here
├── summaries/              ← local markdown summaries are saved here
├── scripts/                ← all automation scripts
│   ├── setup.sh
│   ├── run_uploader.sh
│   ├── analyze_and_upload.py
│   ├── directory_uploader.py
│   ├── confluence_uploader.py
│   ├── smart_uploader.py
│   ├── process_with_claude.py
│   └── process_transcripts.sh
└── .confluence_config.json ← created by setup.sh
```

## Scripts

| Script | Purpose |
|---|---|
| `scripts/setup.sh` | One-time setup: credentials, dependencies, scheduling |
| `scripts/run_uploader.sh` | Entry point wrapper (called by launchd or manually) |
| `scripts/analyze_and_upload.py` | Main pipeline: analyze with Claude then upload |
| `scripts/directory_uploader.py` | Creates/updates Confluence pages with directory |
| `scripts/confluence_uploader.py` | Standalone Confluence uploader with built-in analysis |
| `scripts/smart_uploader.py` | Uploads using pre-generated analyses |
| `scripts/process_with_claude.py` | Prepares transcripts for batch analysis |
| `scripts/process_transcripts.sh` | Shell-based transcript processor |

## Requirements

- Python 3.8+
- macOS (for launchd automation; scripts work on Linux without the agent)
- A Confluence instance with API access
- An Anthropic API key

## Manual Usage

```bash
cd ~/meeting-summarizer-tool
./scripts/run_uploader.sh

# Or run the Python script directly
python3 scripts/analyze_and_upload.py
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

## Customizing the Prompt

The prompt that tells Claude how to analyze transcripts lives in `analyze_and_upload.py` (line ~61). The current prompt is:

```
You are an expert meeting note-taker.

Summarize the following meeting transcript clearly and concisely. Focus on:

- Key decisions made
- Important discussion points and rationale
- Action items, including owner and deadline if mentioned
- Open questions or unresolved issues

Structure the summary with clear section headers. Use bullet points where helpful.
Do not include small talk, repetition, or off-topic discussion.
```

It asks Claude to return four sections: **Key Decisions**, **Discussion Points**, **Action Items**, and **Open Questions**.

To customize it, open `scripts/analyze_and_upload.py` and edit the `prompt = f"""..."""` string inside the `analyze_transcript_with_api` function. You can change what sections are extracted, adjust the tone, or add instructions specific to your team. Just keep the four section headers (`KEY DECISIONS:`, `DISCUSSION POINTS:`, `ACTION ITEMS:`, `OPEN QUESTIONS:`) since the parser expects them — or update the parsing logic below the prompt to match your new headers.

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
