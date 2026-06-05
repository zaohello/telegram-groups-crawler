"""
resolve_links.py v6 — Windows CMD 兼容版
所有输出用 ASCII 字符，避免 GBK 编码报错
"""
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, errors
from telethon.tl.types import Channel, Chat, User

# 强制 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

api_id = 611335
api_hash = 'd524b414d21f4d37f08684c1df41ac9c'
session_name = 'discoverer_session'

PROGRESS_FILE = 'resolve_progress.json'
REQUEST_DELAY = 3.0


def contains_chinese(text):
    if not text:
        return False
    return any('\u4e00' <= c <= '\u9fff' for c in text)


def progress_bar(current, total, width=30):
    filled = int(width * current / max(total, 1))
    bar = '#' * filled + '-' * (width - filled)
    pct = current / max(total, 1) * 100
    return f"[{bar}] {pct:.1f}%"


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'done': {}, 'chinese_groups': [], 'other_groups': []}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


async def countdown(seconds):
    end_time = datetime.now() + timedelta(seconds=seconds)
    remaining = seconds
    while remaining > 0:
        mins, secs = divmod(int(remaining), 60)
        hours, mins = divmod(mins, 60)
        end_str = end_time.strftime("%H:%M:%S")
        if hours > 0:
            print(f"\r    countdown: {hours}h{mins:02d}m{secs:02d}s | resume at {end_str}   ", end="", flush=True)
        else:
            print(f"\r    countdown: {mins}m{secs:02d}s | resume at {end_str}               ", end="", flush=True)
        await asyncio.sleep(30)
        remaining -= 30
    print()


async def main():
    client = TelegramClient(session_name, api_id, api_hash)
    await client.start()

    me = await client.get_me()
    print(f"[OK] logged in: {me.first_name} (@{me.username})")
    print(f"time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: load local cache
    print("Step 1: loading local entity cache...")
    cached_entities = {}
    dialog_count = 0
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, (Channel, Chat)):
            uname = getattr(entity, 'username', None)
            if uname:
                cached_entities[uname.lower()] = entity
            dialog_count += 1
    print(f"  loaded {dialog_count} dialogs, {len(cached_entities)} groups/channels with username\n")

    # read CSV
    links = []
    with open('discovered_links.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            links.append(row)

    total = len(links)

    # load progress
    progress = load_progress()
    done_set = set(progress['done'].keys())
    chinese_groups = progress['chinese_groups']
    other_groups = progress['other_groups']

    # count remaining
    to_process = []
    invite_count = 0
    for row in links:
        if row['type'] == 'private_invite':
            invite_count += 1
        elif row['link'] not in done_set:
            to_process.append(row)

    already_done = len(done_set)
    remaining = len(to_process)
    non_invite = total - invite_count

    print(f"Step 2: resolving links")
    print(f"  total:        {total}")
    print(f"  private(skip):{invite_count}")
    print(f"  done(resume): {already_done}")
    print(f"  remaining:    {remaining}")
    print(f"  {progress_bar(already_done, non_invite)}")
    print()

    stats = {'user': 0, 'chinese_group': 0, 'other_group': 0,
             'not_exist': 0, 'other_error': 0, 'cache_hit': 0}

    for v in progress['done'].values():
        if v in stats:
            stats[v] += 1

    start_time = time.time()
    new_done = 0

    for idx, row in enumerate(to_process):
        identifier = row['link']
        new_done += 1
        current_total = already_done + new_done

        # progress
        bar = progress_bar(current_total, non_invite)
        elapsed = time.time() - start_time
        if new_done > 1:
            eta_per = elapsed / (new_done - 1)
            eta_left = eta_per * (remaining - new_done)
            eta_m = int(eta_left / 60)
            eta_str = f"ETA {eta_m}min" if eta_m > 0 else "almost done"
        else:
            eta_str = "calculating..."

        print(f"  {bar}  ({current_total}/{non_invite})  {eta_str}")
        print(f"    -> {identifier}", end=" ... ", flush=True)

        # check local cache first (no API call)
        cached = cached_entities.get(identifier.lower())
        if cached:
            stats['cache_hit'] += 1
            title = getattr(cached, 'title', '') or ''
            members = getattr(cached, 'participants_count', None)
            is_broadcast = getattr(cached, 'broadcast', False)
            etype = "channel" if is_broadcast else "group"
            uname = getattr(cached, 'username', identifier)

            info = {
                'title': title, 'username': uname,
                'link': f"https://t.me/{uname}",
                'members': members, 'type': etype,
            }

            if contains_chinese(title):
                stats['chinese_group'] += 1
                chinese_groups.append(info)
                print(f"[CACHE] CN {etype}: {title} ({members or '?'})")
                progress['done'][identifier] = 'chinese_group'
            else:
                stats['other_group'] += 1
                other_groups.append(info)
                print(f"[CACHE] {etype}: {title}")
                progress['done'][identifier] = 'other_group'
            continue

        # API call
        resolved = False
        retry = 0

        while not resolved and retry < 3:
            try:
                entity = await client.get_entity(identifier)

                if isinstance(entity, User):
                    stats['user'] += 1
                    name = f"{entity.first_name or ''} {entity.last_name or ''}".strip()
                    print(f"USER: {name}")
                    progress['done'][identifier] = 'user'

                elif isinstance(entity, (Channel, Chat)):
                    title = getattr(entity, 'title', '') or ''
                    members = getattr(entity, 'participants_count', None)
                    is_broadcast = getattr(entity, 'broadcast', False)
                    etype = "channel" if is_broadcast else "group"
                    uname = getattr(entity, 'username', identifier)

                    info = {
                        'title': title, 'username': uname,
                        'link': f"https://t.me/{uname}" if uname else f"https://t.me/{identifier}",
                        'members': members, 'type': etype,
                    }

                    if contains_chinese(title):
                        stats['chinese_group'] += 1
                        chinese_groups.append(info)
                        print(f"CN {etype}: {title} ({members or '?'})")
                        progress['done'][identifier] = 'chinese_group'
                    else:
                        stats['other_group'] += 1
                        other_groups.append(info)
                        print(f"{etype}: {title}")
                        progress['done'][identifier] = 'other_group'
                else:
                    print(f"unknown: {type(entity).__name__}")
                    progress['done'][identifier] = 'other_error'

                resolved = True

            except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError):
                stats['not_exist'] += 1
                print(f"not found")
                progress['done'][identifier] = 'not_exist'
                resolved = True

            except errors.FloodWaitError as e:
                retry += 1
                progress['chinese_groups'] = chinese_groups
                progress['other_groups'] = other_groups
                save_progress(progress)

                resume = datetime.now() + timedelta(seconds=e.seconds + 5)
                print(f"\n    !!! FloodWait: {e.seconds}s ({e.seconds//60}min)")
                print(f"    resume at: {resume.strftime('%H:%M:%S')}")
                print(f"    (progress saved, Ctrl+C safe, will auto-resume next run)")
                await countdown(e.seconds + 5)
                print(f"    wait done, continuing...")

            except Exception as e:
                stats['other_error'] += 1
                print(f"ERR: {type(e).__name__}: {str(e)[:50]}")
                progress['done'][identifier] = 'other_error'
                resolved = True

        if new_done % 5 == 0:
            progress['chinese_groups'] = chinese_groups
            progress['other_groups'] = other_groups
            save_progress(progress)

        await asyncio.sleep(REQUEST_DELAY)

    # final save
    progress['chinese_groups'] = chinese_groups
    progress['other_groups'] = other_groups
    save_progress(progress)

    # summary
    print(f"\n{'='*60}")
    print(f"  DONE!  {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    print(f"  total:        {total}")
    print(f"  private:      {invite_count}")
    print(f"  cache hit:    {stats['cache_hit']}")
    print(f"  users:        {stats['user']}")
    print(f"  CN groups:    {stats['chinese_group']}")
    print(f"  other groups: {stats['other_group']}")
    print(f"  not found:    {stats['not_exist']}")
    print(f"  errors:       {stats['other_error']}")
    total_done = invite_count + sum(stats.values())
    print(f"  accounted:    {total_done} / {total}")
    print(f"{'='*60}\n")

    if chinese_groups:
        chinese_groups.sort(key=lambda x: x.get('members') or 0, reverse=True)
        print("=== Chinese Groups ===\n")
        for g in chinese_groups:
            m = g.get('members') or '?'
            print(f"  [{m}] {g['title']} ({g['type']})")
            print(f"      {g['link']}")

    # save report
    with open('group_report.md', 'w', encoding='utf-8') as f:
        f.write("# Group Discovery Report\n\n")
        f.write(f"| Category | Count |\n|---|---|\n")
        f.write(f"| Total | {total} |\n")
        f.write(f"| Private invite | {invite_count} |\n")
        f.write(f"| Cache hit | {stats['cache_hit']} |\n")
        f.write(f"| Users | {stats['user']} |\n")
        f.write(f"| CN groups | {stats['chinese_group']} |\n")
        f.write(f"| Other groups | {stats['other_group']} |\n")
        f.write(f"| Not found | {stats['not_exist']} |\n")
        f.write(f"| Errors | {stats['other_error']} |\n\n")

        if chinese_groups:
            f.write(f"## Chinese Groups ({len(chinese_groups)})\n\n")
            f.write("| Name | Type | Members | Link |\n|---|---|---|---|\n")
            for g in chinese_groups:
                m = g.get('members') or '?'
                f.write(f"| {g['title']} | {g['type']} | {m} | [{g.get('username','')}]({g['link']}) |\n")

        if other_groups:
            f.write(f"\n## Other Groups ({len(other_groups)})\n\n")
            f.write("| Name | Type | Members | Link |\n|---|---|---|---|\n")
            for g in other_groups:
                m = g.get('members') or '?'
                f.write(f"| {g['title']} | {g['type']} | {m} | [{g.get('username','')}]({g['link']}) |\n")

    print(f"\nReport saved: group_report.md")
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
