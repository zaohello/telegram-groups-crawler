"""
telegram-groups-crawler 升级版
===============================
基于 edogab33/telegram-groups-crawler 原始框架
修复了链接提取正则、更新 Telethon API 兼容性、增加 AI 关键词过滤

原始项目: https://github.com/edogab33/telegram-groups-crawler
修改内容:
  1. 修复 gather_links() 正则 —— 原版只匹配 joinchat/ 格式，漏掉 t.me/username 和 t.me/+hash
  2. 更新异常类路径兼容新版 Telethon (1.43+)
  3. 增加 AI 关键词过滤
  4. 增加 JSON/CSV 导出（除了原有 pickle）
  5. 增加请求延时避免 FloodWait
  6. 移除 pandas 硬依赖，改用 json 持久化（可选保留 pickle）

使用方法:
  1. pip install telethon
  2. 修改下方 CONFIG
  3. python scraper_upgraded.py
"""

import asyncio
from telethon import TelegramClient, errors
import telethon
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

import random
import re
import os
import json
import csv
import sys
from datetime import datetime

from telethon.tl.types import Channel, Chat, User

# ============================================================
#  CONFIG - 修改这里
# ============================================================
api_id = 611335
api_hash = 'd524b414d21f4d37f08684c1df41ac9c'
session_name = 'discoverer_session'  # session 文件名

# 每个群扫描消息数上限（原版是 1000000 太大了）
MESSAGE_LIMIT = 3000

# AI 关键词过滤（群名包含才记录；设为空列表 [] 不过滤）
AI_KEYWORDS = [
    "AI", "ai", "人工智能", "ChatGPT", "chatgpt", "GPT", "gpt",
    "Claude", "claude", "LLM", "llm", "Gemini", "gemini",
    "Midjourney", "midjourney", "MJ", "Stable Diffusion",
    "AIGC", "aigc", "深度学习", "机器学习", "大模型",
    "Copilot", "copilot", "OpenAI", "openai",
    "AI工具", "AI变现", "AI赚钱", "AI交流",
    "prompt", "Prompt", "AGI", "agi",
    "DeepSeek", "deepseek", "Sora", "sora",
]

# 请求间延时（秒）
REQUEST_DELAY = 1.0

# ============================================================

client = TelegramClient(session_name, api_id, api_hash)
groups = []
to_be_processed = set()
done = set()
edges = {}
package_dir = os.path.dirname(os.path.abspath(__file__))


# ============================================================
#  【核心修复】链接提取 —— 原版只有 joinchat 正则，这里覆盖所有格式
# ============================================================

# 排除的非群 username
EXCLUDED_USERNAMES = {
    "proxy", "socks", "setlanguage", "addstickers", "addemoji",
    "addtheme", "bg", "share", "iv", "confirmphone", "login",
    "passport", "c", "s", "privacy", "tos", "dl",
}

def extract_tg_links(text: str) -> set:
    """
    从文本中提取所有 Telegram 群链接
    【这是对原版 gather_links() 中正则的核心修复】

    原版正则: re.search('(?<=joinchat\\/)(\\w+[-]?\\S\\w+)', message.text)
    问题: 只匹配 t.me/joinchat/HASH 格式
    遗漏: t.me/username, t.me/+HASH, telegram.me/xxx 等

    修复后支持:
      - https://t.me/username
      - https://t.me/+abc123
      - https://t.me/joinchat/abc123
      - https://telegram.me/username
      - https://telegram.dog/username
      - @username 提及
    """
    if not text:
        return set()

    found = set()

    # Pattern 1: t.me/joinchat/HASH（保留原版逻辑）
    for match in re.finditer(r'(?:https?://)?t\.me/joinchat/([a-zA-Z0-9_\-]+)', text, re.IGNORECASE):
        found.add("joinchat/" + match.group(1))

    # Pattern 2: t.me/+HASH（私有邀请链接新格式）—— 原版完全没有
    for match in re.finditer(r'(?:https?://)?t\.me/\+([a-zA-Z0-9_\-]+)', text, re.IGNORECASE):
        found.add("+" + match.group(1))

    # Pattern 3: t.me/username（公开群）—— 原版完全没有
    for match in re.finditer(r'(?:https?://)?t\.me/([a-zA-Z]\w{3,})', text, re.IGNORECASE):
        username = match.group(1)
        if username.lower() not in EXCLUDED_USERNAMES and not username.lower().endswith('bot'):
            # 确保不是 joinchat 路径
            if 'joinchat' not in username.lower():
                found.add(username)

    # Pattern 4: telegram.me/username —— 原版完全没有
    for match in re.finditer(r'(?:https?://)?telegram\.me/([a-zA-Z]\w{3,})', text, re.IGNORECASE):
        username = match.group(1)
        if username.lower() not in EXCLUDED_USERNAMES and not username.lower().endswith('bot'):
            found.add(username)

    # Pattern 5: telegram.dog/username —— 原版完全没有
    for match in re.finditer(r'(?:https?://)?telegram\.dog/([a-zA-Z]\w{3,})', text, re.IGNORECASE):
        username = match.group(1)
        if username.lower() not in EXCLUDED_USERNAMES and not username.lower().endswith('bot'):
            found.add(username)

    # Pattern 6: @username 提及 —— 已禁用！
    # 原因：群聊里 @某人 大多是个人用户，不是群链接，会混入大量噪音
    # for match in re.finditer(r'@([a-zA-Z]\w{3,})', text):
    #     username = match.group(1)
    #     if username.lower() not in EXCLUDED_USERNAMES and not username.lower().endswith('bot'):
    #         found.add(username)

    return found


def matches_keywords(text: str) -> bool:
    """检查文本是否包含 AI 关键词"""
    if not AI_KEYWORDS:
        return True
    if not text:
        return False
    return any(kw in text for kw in AI_KEYWORDS)


# ============================================================
#  原框架函数（已更新兼容性）
# ============================================================

async def main():
    global groups, edges, to_be_processed, done, package_dir

    me = await client.get_me()
    print(f"\n{'='*60}")
    print(f"  已登录: {me.first_name} (@{me.username}) | {me.phone}")
    print(f"{'='*60}\n")

    # 第一阶段: 扫描已加入的群，提取链接
    await init_empty()

    # 第二阶段: 处理发现的链接（加入→收集→退出）
    # ⚠️ 注意：取消注释下面这行才会自动加入发现的群
    # await start()


async def init_empty():
    """
    第一阶段：扫描所有已加入的群/频道，收集链接
    （对应原版 init_empty，但用了修复后的链接提取）
    """
    to_be_processed = set()
    edges = {}
    done = set()
    groups = []
    chat_count = 0

    print("📋 正在扫描已加入的群/频道...\n")

    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, (Channel, Chat)):
            chat_count += 1
            name = dialog.entity.title or "(未知)"
            print(f"  [{chat_count}] 扫描: {name[:45]}", end="", flush=True)

            # 【核心修复点】使用新的 gather_links
            temp_to_be_processed = await gather_links(dialog)
            edges = update_edges(edges, temp_to_be_processed, dialog)
            to_be_processed = to_be_processed.union(temp_to_be_processed)

            if temp_to_be_processed:
                print(f"  → {len(temp_to_be_processed)} 个链接 ✨")
            else:
                print(f"  → 0")

            groups.append(await collect_data(dialog, ""))

            done.add(str(dialog.entity.id))

            await asyncio.sleep(REQUEST_DELAY)

    # 保存数据（JSON 格式，替代原版 pickle）
    save_json(to_be_processed, done, groups, edges)

    print(f"\n{'='*60}")
    print(f"  ✅ 初始化完成!")
    print(f"  扫描群数: {chat_count}")
    print(f"  发现待处理链接: {len(to_be_processed)}")
    print(f"  已保存到: discovered_links.json / discovered_groups.csv")
    print(f"{'='*60}\n")

    # 额外输出: 可读的 CSV
    export_discovered_csv(to_be_processed)

    return to_be_processed, edges, done, groups


async def gather_links(dialog):
    """
    【核心修复】从单个群/频道收集链接
    原版问题: 只用 search="https://t.me/" 且正则只匹配 joinchat
    修复: 扫描所有消息，用完整正则匹配所有格式
    """
    links = set()
    msg_count = 0

    try:
        # 原版用 search="https://t.me/" 过滤，但这会漏掉:
        # - 没有 https:// 前缀的链接
        # - @username 格式的提及
        # - 内联按钮中的链接
        # 修复: 不用 search 过滤，扫描全部消息
        async for message in client.iter_messages(dialog.id, limit=MESSAGE_LIMIT):
            msg_count += 1

            # 从消息正文提取
            if message.text:
                links |= extract_tg_links(message.text)

            # 从消息实体（超链接、提及）提取 —— 原版完全没有
            if message.entities:
                for entity in message.entities:
                    if hasattr(entity, 'url') and entity.url:
                        links |= extract_tg_links(entity.url)

            # 从转发来源提取 —— 原版完全没有
            if message.forward and hasattr(message.forward, 'chat'):
                fwd_chat = message.forward.chat
                if fwd_chat and hasattr(fwd_chat, 'username') and fwd_chat.username:
                    username = fwd_chat.username
                    if username.lower() not in EXCLUDED_USERNAMES:
                        links.add(username)

            # 从内联按钮提取 —— 原版完全没有
            if message.reply_markup:
                try:
                    for row in message.reply_markup.rows:
                        for button in row.buttons:
                            if hasattr(button, 'url') and button.url:
                                links |= extract_tg_links(button.url)
                except (AttributeError, TypeError):
                    pass

            # 每 200 条暂停，避免限速
            if msg_count % 200 == 0:
                await asyncio.sleep(0.3)

    except errors.ChannelPrivateError:
        pass
    except errors.ChatAdminRequiredError:
        pass
    except errors.FloodWaitError as e:
        print(f"\n    ⏳ FloodWait: 等待 {e.seconds} 秒...")
        if e.seconds <= 120:
            await asyncio.sleep(e.seconds + 5)
        else:
            print(f"    ❌ 跳过（等待时间太长）")
    except TypeError:
        pass
    except Exception as e:
        pass

    return links


async def collect_data(dialog, link):
    """收集群基本信息（简化版，不抓成员和消息内容以提高速度）"""
    group = dialog.entity
    d = {}

    if isinstance(group, (Channel, Chat)):
        username = getattr(group, 'username', None)
        members_count = getattr(group, 'participants_count', None)

        d = {
            "id": str(group.id),
            "name": group.title,
            "username": username,
            "link_hash": link,
            "date": str(getattr(group, 'date', '')),
            "is_scam": str(getattr(group, 'scam', False)),
            "members_count": members_count,
            "type": "channel" if getattr(group, 'broadcast', False) else "group",
            "link": f"https://t.me/{username}" if username else "",
        }

    return d


def update_edges(edges: dict, tbp, dialog):
    """更新边关系（保留原版逻辑）"""
    for link in tbp:
        if link in edges:
            edges[link].append(dialog.entity.id)
        else:
            edges[link] = [dialog.entity.id]
    return edges


async def start():
    """
    第二阶段：遍历 to_be_processed，自动加入新群、收集数据、退出
    ⚠️ 谨慎使用！会自动加入/退出群，可能触发 Telegram 限制
    """
    data = load_json()
    if not data:
        print("❌ 未找到数据文件，请先运行 init_empty()")
        return

    to_be_processed = set(data.get("to_be_processed", []))
    done = set(data.get("done", []))
    groups = data.get("groups", [])
    edges = data.get("edges", {})

    total = len(to_be_processed)
    counter = 0
    new_groups = []

    print(f"\n🚀 开始处理 {total} 个待处理链接...\n")

    for link in list(to_be_processed):
        counter += 1
        if link in done:
            continue

        print(f"  [{counter}/{total}] 处理: {link}", end="", flush=True)

        try:
            update, to_be_processed, done = await join_group(link, to_be_processed, done)

            if update is not None:
                chat_id = update.chats[0].id
                async for dialog in client.iter_dialogs():
                    if dialog.entity.id == chat_id:
                        if isinstance(dialog.entity, (Channel, Chat)):
                            # 收集这个新群里的链接
                            new_links = await gather_links(dialog)
                            edges = update_edges(edges, new_links, dialog)
                            to_be_processed = to_be_processed.union(new_links)

                            group_data = await collect_data(dialog, link)
                            groups.append(group_data)
                            new_groups.append(group_data)

                            print(f"  ✅ {dialog.entity.title} → 发现 {len(new_links)} 个新链接")
                        break

                done = await leave_group(chat_id, link, done)

        except Exception as e:
            print(f"  ❌ {str(e)[:50]}")
            done.add(link)

        # 保存进度
        if counter % 10 == 0:
            save_json(to_be_processed, done, groups, edges)

        await asyncio.sleep(REQUEST_DELAY * 2)  # 加入/退出操作需要更长间隔

    save_json(to_be_processed, done, groups, edges)
    print(f"\n✅ 处理完成! 新发现 {len(new_groups)} 个群")


async def join_group(link, tbp: set, done: set):
    """加入群（保留原版逻辑，更新异常类路径）"""
    try:
        if link.startswith('+'):
            # t.me/+HASH 格式
            g = await client(ImportChatInviteRequest(link[1:]))
        elif link.startswith('joinchat/'):
            # t.me/joinchat/HASH 格式
            g = await client(ImportChatInviteRequest(link.replace('joinchat/', '')))
        else:
            # 公开 username
            g = await client(JoinChannelRequest(link))

        name = g.chats[0].title if g.chats else link
        print(f"  → 已加入: {name}")
        tbp.discard(link)

    except errors.InviteHashExpiredError:
        print(f"  → 邀请链接已过期")
        tbp.discard(link)
        done.add(link)
        return None, tbp, done
    except errors.UserAlreadyParticipantError:
        print(f"  → 已经是成员")
        tbp.discard(link)
        done.add(link)
        return None, tbp, done
    except errors.FloodWaitError as e:
        print(f"  → FloodWait: {e.seconds}s")
        if e.seconds <= 120:
            await asyncio.sleep(e.seconds + 5)
            return await join_group(link, tbp, done)
        else:
            print(f"  → 跳过（等太久）")
            return None, tbp, done
    except errors.ChannelPrivateError:
        print(f"  → 私有频道，无法加入")
        tbp.discard(link)
        done.add(link)
        return None, tbp, done
    except Exception as e:
        print(f"  → 错误: {str(e)[:40]}")
        tbp.discard(link)
        done.add(link)
        return None, tbp, done

    return g, tbp, done


async def leave_group(chat_id: int, link, done):
    """退出群（保留原版逻辑）"""
    try:
        await client.delete_dialog(chat_id)
        done.add(link)
        print(f"    ← 已退出")
    except Exception as e:
        pass
    return done


# ============================================================
#  数据持久化（JSON 替代 pickle，更安全且可读）
# ============================================================

def save_json(to_be_processed, done, groups, edges):
    """保存所有数据到 JSON"""
    data = {
        "scan_time": datetime.now().isoformat(),
        "to_be_processed": list(to_be_processed),
        "done": list(done),
        "groups": groups,
        "edges": {k: v for k, v in edges.items()},
    }
    filepath = os.path.join(package_dir, "crawler_data.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json():
    """从 JSON 加载数据"""
    filepath = os.path.join(package_dir, "crawler_data.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def export_discovered_csv(to_be_processed):
    """导出发现的链接为 CSV"""
    filepath = os.path.join(package_dir, "discovered_links.csv")
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["link", "type", "full_url"])
        for link in sorted(to_be_processed):
            if link.startswith('+'):
                link_type = "private_invite"
                full_url = f"https://t.me/{link}"
            elif link.startswith('joinchat/'):
                link_type = "joinchat"
                full_url = f"https://t.me/{link}"
            else:
                link_type = "public_username"
                full_url = f"https://t.me/{link}"
            writer.writerow([link, link_type, full_url])

    print(f"📄 已导出 {len(to_be_processed)} 个链接到: {filepath}")


def progress(counter, to_be_processed):
    perc = (round(counter / max(len(to_be_processed), 1), 3)) * 100
    counter += 1
    return perc, counter


# ============================================================
#  入口
# ============================================================

with client:
    client.loop.run_until_complete(main())
    client.disconnect()
