import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
email_file = Path(r"E:\data-export\processed\parsed_emails.json")

if not email_file.exists():
    print("Email file not found.")
    sys.exit(1)

with open(email_file, "r", encoding="utf-8") as f:
    data = json.load(f)

matches = []
keywords = ["laundering", "mixer", "laundr", "tbtc", "mixer", "tumbler", "tornado", "obfusc", "layering"]

for email in data:
    subject = email.get("subject", "") or ""
    body = email.get("body", "") or ""
    
    # Check if any keyword matches
    found = False
    matched_word = ""
    for k in keywords:
        if k in subject.lower() or k in body.lower():
            found = True
            matched_word = k
            break
            
    if found:
        # Filter out noisy automated emails containing long tracking URLs
        if any(len(word) > 100 for word in body.split()):
            continue
        matches.append((email, matched_word))

print(f"Found {len(matches)} clean matching emails:\n")
for email, kw in matches:
    print(f"Subject: {email.get('subject')}")
    print(f"From: {email.get('from')}")
    print(f"To: {email.get('to')}")
    print(f"Date: {email.get('date')}")
    print(f"Matched Keyword: {kw}")
    print(f"Body Snippet:\n{email.get('body')[:500]}")
    print("-" * 60)
