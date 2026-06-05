import asyncio
import csv
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User
from telethon.errors import UsernameNotOccupiedError, UsernameInvalidError

api_id = 611335
api_hash = 'd524b414d21f4d37f08684c1df41ac9c'
phone = '+959663617728'
session_name = 'discoverer_session'

# 关键词过滤
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

def contains_chinese(text):
    if not text:
        return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def matches_ai_keywords(text):
    if not text:
        return False
    return any(kw in text for kw in AI_KEYWORDS)

async def main():
    client = TelegramClient(session_name, api_id, api_hash)
    await client.start(phone=phone)
    
    print("已登录，正在解析 links...")
    
    links = []
    with open('discovered_links.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            links.append(row['link'])
            
    results = []
    for i, identifier in enumerate(links):
        print(f"[{i+1}/{len(links)}] 解析: {identifier}")
        try:
            entity = await client.get_entity(identifier)
            if isinstance(entity, (Channel, Chat)):
                title = getattr(entity, 'title', '')
                members = getattr(entity, 'participants_count', '?')
                
                # 检查是否包含中文
                if contains_chinese(title):
                    print(f"  👉 发现目标: {title} ({members} 成员)")
                    results.append({
                        'title': title,
                        'link': f"https://t.me/{identifier}",
                        'members': members
                    })
            await asyncio.sleep(0.5)
        except Exception as e:
            pass
            
    print("\n--- 整理结果: 中文 AI 群 ---")
    for r in results:
        print(f"[{r['members']} 成员] {r['title']} : {r['link']}")

if __name__ == '__main__':
    asyncio.run(main())
