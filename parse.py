import json

with open('/Users/surendran/.gemini/antigravity/brain/6d320f6f-3859-4b58-bb6d-2e7639eb1fea/.system_generated/steps/210/output.txt') as f:
    data = json.load(f)
for issue in data.get('issues', []):
    title = issue.get('title', '').lower()
    desc = issue.get('description', '').lower()
    if 'wikipedia' in title or 'wikipedia' in desc or 'mcp' in title:
        print(issue['id'], '-', issue['title'])
