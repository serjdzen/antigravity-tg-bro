#!/usr/bin/env python3
"""
Pre-Flight Security & Secret Leak Scanner
Scans all tracked/staged repository files for sensitive credentials, personal paths, or leaked keys before git commits.
"""

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Regex patterns for sensitive information
PATTERNS = {
    "Telegram Bot Token": re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_-]{35}\b"),
    "Groq API Key": re.compile(r"\bgsk_[A-Za-z0-9]{40,}\b"),
    "Google API Key": re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b"),
    "OpenAI API Key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "Hardcoded /Users/ path": re.compile(r"/Users/[a-zA-Z0-9_-]+/Documents"),
}

# Directories and files ignored (as covered by .gitignore)
IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "logs", "uploads"}
IGNORED_FILES = {".bot.env", ".env", "sessions.json"}


def scan_file(file_path: Path) -> list[str]:
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return [f"Could not read file: {e}"]

    for line_num, line in enumerate(content.splitlines(), start=1):
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                # Allow .env.example dummy values
                if file_path.name == ".env.example" and "1234567890:ABCdef" in line:
                    continue
                findings.append(f"[{label}] Line {line_num}: {line.strip()[:60]}...")

    return findings


def run_security_check() -> int:
    print("🔍 Running Pre-Flight Security & Leak Scan...")
    total_scanned = 0
    total_issues = 0

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            if file in IGNORED_FILES or file.endswith(".pyc") or file.endswith(".log"):
                continue

            file_path = Path(root) / file
            rel_path = file_path.relative_to(ROOT_DIR)

            total_scanned += 1
            issues = scan_file(file_path)
            if issues:
                print(f"\n❌ Leaks found in {rel_path}:")
                for issue in issues:
                    print(f"   ⚠️ {issue}")
                    total_issues += 1

    print(f"\n📊 Summary: Scanned {total_scanned} files.")
    if total_issues == 0:
        print("✅ 100% CLEAN: No leaked tokens, hardcoded user paths, or sensitive keys detected!")
        return 0
    else:
        print(f"🚨 FAILED: Found {total_issues} potential security issues. Fix before committing.")
        return 1


if __name__ == "__main__":
    sys.exit(run_security_check())
