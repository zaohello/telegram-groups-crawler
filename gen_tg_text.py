"""
生成可以直接粘贴到 Telegram "已保存的消息" 的链接列表
Telegram 会自动预览每个链接，显示是人/群/频道
"""
import csv

links = []
with open('discovered_links.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        links.append(row)

public = [l for l in links if l['type'] == 'public_username']
private = [l for l in links if l['type'] == 'private_invite']

# 生成公开链接文本（每行一个，方便 Telegram 预览）
# 分批生成，每批 20 个（太多一次发 Telegram 会卡）
batch_size = 20
batch_num = 0

with open('links_for_telegram.txt', 'w', encoding='utf-8') as f:
    f.write(f"=== 公开链接 ({len(public)} 个) ===\n")
    f.write(f"每批 {batch_size} 个，分批粘贴到 Telegram 已保存的消息\n")
    f.write(f"Telegram 会自动显示预览：头像+名称 = 群/频道，人形图标 = 个人用户\n\n")

    for i, link in enumerate(public):
        if i % batch_size == 0:
            batch_num += 1
            f.write(f"\n--- 第 {batch_num} 批 (No.{i+1}-{min(i+batch_size, len(public))}) ---\n\n")
        f.write(f"https://t.me/{link['link']}\n")

    if private:
        f.write(f"\n\n=== 私有邀请链接 ({len(private)} 个) ===\n\n")
        for link in private:
            f.write(f"{link['full_url']}\n")

print(f"Done!")
print(f"  Public:  {len(public)} links")
print(f"  Private: {len(private)} links")
print(f"  Batches: {batch_num} (each {batch_size} links)")
print()
print(f"File: links_for_telegram.txt")
print()
print(f"How to use:")
print(f"  1. Open Telegram -> Saved Messages")
print(f"  2. Copy one batch from the txt file")
print(f"  3. Paste into Saved Messages")
print(f"  4. Telegram shows preview for each link")
print(f"  5. Groups/Channels show name + avatar")
print(f"  6. Personal users show person icon")
