#!/usr/bin/env python3
"""PreToolUse guard for Bash: enforces CLAUDE.md rules that must never be skipped.

Exit code 2 blocks the tool call and shows stderr to Claude.
"""
import json
import re
import subprocess
import sys

payload = json.load(sys.stdin)
command = payload.get("tool_input", {}).get("command", "")

# Permission deny rules only cover the Read tool; `cat .env` via Bash would slip past.
# Template files are safe to read.
SECRET_FILE = re.compile(r"(^|[\s/'\"=<])\.env(\.(?!example\b|sample\b|template\b)[\w.-]+)?(?=$|[\s'\";|&)>])")
if SECRET_FILE.search(command):
    print("Blocked: this command touches a .env file. Secrets stay out of the context window; ask the user instead.", file=sys.stderr)
    sys.exit(2)

# Eval separation (CLAUDE.md): the builder must not read held-out eval code or data.
# Running the frozen loop/metrics on a held-out customer is allowed (it scores
# against the answer key without printing it); inspecting it is not.
HELDOUT = re.compile(r"datagen/heldout|heldout_\w*")
INSPECT = re.compile(r"\b(cat|less|more|head|tail|sed|awk|grep|rg|find|ls|cp|mv|vi|vim|nano|"
                     r"open|strings|xxd)\b|python3?\s+-c\b|python3?\s+-(\s|$)|<<|eval_db|fde_eval")
if HELDOUT.search(command) and INSPECT.search(command):
    print("Blocked: held-out eval code/data is off-limits to the builder (eval separation). "
          "Run the frozen loop or metrics scripts instead, or ask the user.", file=sys.stderr)
    sys.exit(2)

if re.search(r"\bgit\b[^;&|]*\bcommit\b", command):
    branch = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True, cwd=payload.get("cwd")
    ).stdout.strip()
    if branch in ("main", "master"):
        print(f"Blocked: committing directly to '{branch}'. Create a branch first.", file=sys.stderr)
        sys.exit(2)

sys.exit(0)
