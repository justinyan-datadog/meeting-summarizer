#!/usr/bin/env python3
"""
Integrated script that analyzes new transcripts and uploads them to Confluence
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
import subprocess

MEETINGS_DIR = Path(__file__).resolve().parent
ANALYSES_FILE = MEETINGS_DIR / ".transcript_analyses.json"
CONFIG_FILE = MEETINGS_DIR / ".confluence_config.json"
SUMMARIES_DIR = MEETINGS_DIR / "summaries"

def load_config():
    """Load configuration."""
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def load_analyses():
    """Load existing analyses."""
    if ANALYSES_FILE.exists():
        with open(ANALYSES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_analyses(analyses):
    """Save analyses to file."""
    with open(ANALYSES_FILE, 'w') as f:
        json.dump(analyses, f, indent=2)

def markdown_to_html(text):
    """Convert basic markdown formatting to HTML."""
    # Convert bold (**text** or __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Convert italic (*text* or _text_) - but not if it's part of a word
    text = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'<em>\1</em>', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<em>\1</em>', text)
    # Convert inline code (`text`)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text

def save_summary_to_file(filename, analysis):
    """Write analysis as a markdown file to the summaries/ folder."""
    SUMMARIES_DIR.mkdir(exist_ok=True)
    stem = Path(filename).stem
    output_path = SUMMARIES_DIR / f"{stem}.md"

    sections = [
        ("Key Decisions", analysis.get("key_decisions", [])),
        ("Discussion Points", analysis.get("discussion_points", [])),
        ("Action Items", analysis.get("action_items", [])),
        ("Open Questions", analysis.get("open_questions", [])),
    ]

    lines = [f"# {stem}\n"]
    for title, items in sections:
        lines.append(f"## {title}\n")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.append("")

    output_path.write_text("\n".join(lines))
    print(f"   Summary saved to summaries/{stem}.md")


def analyze_transcript_with_api(filepath, api_key):
    """
    Use Anthropic API to analyze a transcript.
    Returns analysis dict or None on error.
    """
    print(f"   Analyzing with Claude API...")

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        content = filepath.read_text()

        prompt = f"""You are an expert meeting note-taker.

Summarize the following meeting transcript clearly and concisely. Focus on:

- Key decisions made
- Important discussion points and rationale
- Action items, including owner and deadline if mentioned
- Open questions or unresolved issues

Structure the summary with clear section headers. Use bullet points where helpful.
Do not include small talk, repetition, or off-topic discussion.
You may use markdown formatting like **bold** or *italic* to emphasize key points.

Format your response exactly as follows:

KEY DECISIONS:
[Bullet points of key decisions made, or "None" if no decisions were made]

DISCUSSION POINTS:
[Bullet points of important discussion points and their rationale]

ACTION ITEMS:
[Bullet points of action items with owner and deadline if mentioned, or "None" if no action items]

OPEN QUESTIONS:
[Bullet points of unresolved issues or open questions, or "None" if no open questions]

Here is the transcript to analyze:

{content}
"""

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response = message.content[0].text

        # Parse the response
        decisions_match = re.search(r'KEY DECISIONS:\s*(.*?)(?=DISCUSSION POINTS:|$)', response, re.DOTALL | re.IGNORECASE)
        discussion_match = re.search(r'DISCUSSION POINTS:\s*(.*?)(?=ACTION ITEMS:|$)', response, re.DOTALL | re.IGNORECASE)
        action_items_match = re.search(r'ACTION ITEMS:\s*(.*?)(?=OPEN QUESTIONS:|$)', response, re.DOTALL | re.IGNORECASE)
        questions_match = re.search(r'OPEN QUESTIONS:\s*(.*?)$', response, re.DOTALL | re.IGNORECASE)

        def extract_bullets(text):
            """Extract bullet points from text."""
            if not text:
                return []
            items = []
            for line in text.strip().split('\n'):
                line = line.strip()
                if line and (line.startswith('-') or line.startswith('*')):
                    # Remove the bullet point
                    item = re.sub(r'^[-*]\s*', '', line)
                    if item.lower() != 'none':
                        # Convert markdown to HTML
                        item = markdown_to_html(item)
                        items.append(item)
            return items

        if decisions_match or discussion_match or action_items_match or questions_match:
            analysis = {
                "key_decisions": extract_bullets(decisions_match.group(1) if decisions_match else ""),
                "discussion_points": extract_bullets(discussion_match.group(1) if discussion_match else ""),
                "action_items": extract_bullets(action_items_match.group(1) if action_items_match else ""),
                "open_questions": extract_bullets(questions_match.group(1) if questions_match else "")
            }
            return analysis

        print(f"   Warning: Failed to parse API response")
        return None

    except ImportError:
        print("   Error: 'anthropic' package not installed.")
        print("   Run: pip3 install anthropic")
        print("   Or re-run setup.sh")
        return None
    except Exception as e:
        print(f"   Error: API error: {e}")
        return None

def main():
    print("Checking for new transcripts to analyze...\n")

    config = load_config()
    api_key = config.get('anthropic_api_key')

    if not api_key:
        print("Error: No Anthropic API key configured!")
        return 1

    analyses = load_analyses()
    new_analyses = False

    # Find all .txt files
    for txt_file in MEETINGS_DIR.glob("*.txt"):
        filename = txt_file.name

        # Skip if already analyzed
        if filename in analyses:
            continue

        # Skip system files
        if filename.startswith('.') or filename.startswith('EXAMPLE') or filename.startswith('Test'):
            continue

        print(f"New transcript found: {filename}")

        try:
            analysis = analyze_transcript_with_api(txt_file, api_key)

            if analysis:
                analyses[filename] = analysis
                new_analyses = True
                save_summary_to_file(filename, analysis)
                print(f"   Analysis complete!\n")
            else:
                print(f"   Analysis failed - skipping this file\n")

        except Exception as e:
            print(f"   Error analyzing: {e}\n")

    if new_analyses:
        save_analyses(analyses)
        print(f"Saved {len([k for k in analyses.keys()])} total analyses\n")

        # Now run the uploader
        print("Running uploader...\n")
        try:
            result = subprocess.run(
                [sys.executable, str(MEETINGS_DIR / "directory_uploader.py")],
                capture_output=True,
                text=True,
                cwd=str(MEETINGS_DIR)
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr)

            return result.returncode
        except Exception as e:
            print(f"Error: Upload error: {e}")
            return 1
    else:
        print("No new transcripts to analyze")
        return 0

if __name__ == "__main__":
    sys.exit(main())
