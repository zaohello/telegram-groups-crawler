"""
生成可点击的 HTML 页面，让用户手动查看哪些是中文群
不需要任何 API 调用，不触发 FloodWait
"""
import csv

links = []
with open('discovered_links.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        links.append(row)

html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Telegram Links Browser</title>
<style>
body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }
h1 { color: #0088cc; }
.stats { background: #16213e; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
.link-card { background: #16213e; margin: 8px 0; padding: 12px 15px; border-radius: 6px; display: flex; align-items: center; justify-content: space-between; }
.link-card:hover { background: #1a1a4e; }
.link-card a { color: #00b4d8; text-decoration: none; font-size: 16px; }
.link-card a:hover { text-decoration: underline; }
.type-tag { font-size: 12px; padding: 3px 8px; border-radius: 4px; }
.type-public { background: #2d6a4f; color: #b7e4c7; }
.type-private { background: #6a2d2d; color: #e4b7b7; }
.idx { color: #666; width: 40px; }
.open-btn { background: #0088cc; color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; }
.open-btn:hover { background: #006699; }
.section { margin-top: 30px; }
h2 { color: #aaa; border-bottom: 1px solid #333; padding-bottom: 5px; }
</style>
</head>
<body>
<h1>Telegram Discovered Links</h1>
<div class="stats">
"""

public_links = [l for l in links if l['type'] == 'public_username']
private_links = [l for l in links if l['type'] == 'private_invite']

html += f"<p>Total: <b>{len(links)}</b> | Public: <b>{len(public_links)}</b> | Private invite: <b>{len(private_links)}</b></p>"
html += f"<p>Click each link to open in Telegram and check if it's a Chinese AI group.</p>"
html += "</div>\n"

# Public links
html += '<div class="section"><h2>Public Links (click to check)</h2>\n'
for i, link in enumerate(public_links, 1):
    url = link['full_url']
    name = link['link']
    html += f'''<div class="link-card">
  <span class="idx">{i}.</span>
  <a href="{url}" target="_blank">{name}</a>
  <span class="type-tag type-public">public</span>
  <a href="{url}" target="_blank" class="open-btn">Open in TG</a>
</div>\n'''

# Private links
html += '</div>\n<div class="section"><h2>Private Invite Links</h2>\n'
for i, link in enumerate(private_links, 1):
    url = link['full_url']
    name = link['link']
    html += f'''<div class="link-card">
  <span class="idx">{i}.</span>
  <a href="{url}" target="_blank">{name}</a>
  <span class="type-tag type-private">private</span>
  <a href="{url}" target="_blank" class="open-btn">Open in TG</a>
</div>\n'''

html += "</div>\n</body></html>"

with open('links_browser.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Done! Generated links_browser.html")
print(f"  Public links:  {len(public_links)}")
print(f"  Private links: {len(private_links)}")
print(f"Open links_browser.html in your browser to check each link.")
