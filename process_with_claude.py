#!/usr/bin/env python3
"""
Meeting Transcript Processor - Local Mode
Uses Claude Code to generate summaries and action items
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

MEETINGS_DIR = Path(__file__).resolve().parent
STATE_FILE = MEETINGS_DIR / ".processed_transcripts.json"
ANALYSIS_DIR = MEETINGS_DIR / ".analyses"

# Create analysis directory
ANALYSIS_DIR.mkdir(exist_ok=True)

def load_state():
    """Load processing state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"processed": []}

def get_unprocessed_transcripts():
    """Get list of transcript files that haven't been processed."""
    state = load_state()
    processed_files = [item["filename"] if isinstance(item, dict) else item
                       for item in state.get("processed", [])]

    transcript_files = list(MEETINGS_DIR.glob("*.txt"))
    # Skip example and hidden files
    transcript_files = [f for f in transcript_files
                       if not f.name.startswith('.')
                       and not f.name.startswith('EXAMPLE')]

    unprocessed = [f for f in transcript_files if f.name not in processed_files]
    return unprocessed

def save_transcript_for_analysis(filename, content):
    """Save transcript and prepare for Claude analysis."""
    analysis_file = ANALYSIS_DIR / f"{filename}.analysis.txt"

    with open(analysis_file, 'w') as f:
        f.write("TRANSCRIPT TO ANALYZE:\n")
        f.write("=" * 80 + "\n\n")
        f.write(content)
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("INSTRUCTIONS:\n")
        f.write("Please provide:\n")
        f.write("1. SUMMARY: A concise 2-3 sentence summary of the meeting\n")
        f.write("2. ACTION ITEMS: A bulleted list of clear action items with owners\n")
        f.write("\n")
        f.write("Format your response as:\n")
        f.write("SUMMARY:\n")
        f.write("[your summary]\n")
        f.write("\n")
        f.write("ACTION ITEMS:\n")
        f.write("- [action item 1]\n")
        f.write("- [action item 2]\n")

    return analysis_file

def main():
    print("Checking for unprocessed transcripts...")

    unprocessed = get_unprocessed_transcripts()

    if not unprocessed:
        print("No new transcripts to process!")
        return

    print(f"Found {len(unprocessed)} transcript(s) to analyze:\n")

    for transcript_file in unprocessed:
        print(f"   - {transcript_file.name}")

    print(f"\nTranscripts ready for analysis in: {ANALYSIS_DIR}")
    print(f"\nNext step: Run the batch processor to analyze all at once!")
    print(f"   Or analyze them individually in {ANALYSIS_DIR}\n")

if __name__ == "__main__":
    main()
