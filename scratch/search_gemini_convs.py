import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
conv_file = Path(r"E:\data-export\processed\gemini_full_activity.json")

if not conv_file.exists():
    conv_file = Path(r"E:\data-export\processed\gemini_conversations.json")

if not conv_file.exists():
    print("Gemini conversations file not found.")
    sys.exit(1)

print(f"Loading conversations from {conv_file}...")
with open(conv_file, "r", encoding="utf-8", errors="replace") as f:
    data = json.load(f)

if isinstance(data, dict) and "conversations" in data:
    conversations = data["conversations"]
else:
    conversations = data

print(f"Loaded {len(conversations)} conversations.")

keywords = ["laundering", "money laundering", "mixer", "tornado cash", "tumbler", "shell company", "tax evasion", "wash trading", "smurfing", "structuring", "fraud", "credit card"]
matches = []

for idx, item in enumerate(conversations):
    text_content = ""
    if isinstance(item, dict):
        text_content = " ".join([str(val) for val in item.values()])
    elif isinstance(item, list):
        text_content = " ".join([str(val) for val in item])
    else:
        text_content = str(item)
        
    found = False
    matched_word = ""
    for kw in keywords:
        if kw in text_content.lower():
            found = True
            matched_word = kw
            break
            
    if found:
        matches.append((item, matched_word, idx))

print(f"Found {len(matches)} matching conversations:\n")
for item, kw, idx in matches[:15]:
    print(f"Match index: {idx} | Keyword: {kw}")
    if isinstance(item, dict):
        # Print prompt/title or snippet
        prompt = item.get("prompt", item.get("title", item.get("query", "")))
        if not prompt and "parts" in item:
            # Maybe it contains parts
            parts = item["parts"]
            prompt = parts[0].get("text", "") if parts else ""
        if not prompt:
            prompt = str(item)[:150]
        print(f"Prompt/Title: {prompt}")
        
        response = item.get("response", item.get("body", item.get("content", "")))
        if not response and "parts" in item:
            parts = item["parts"]
            response = " ".join([p.get("text", "") for p in parts[1:]]) if len(parts) > 1 else ""
        if response:
            print(f"Response Snippet: {response[:300]}...")
    else:
        print(f"Content: {str(item)[:300]}...")
    print("-" * 60)
