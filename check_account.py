import asyncio
from telethon import TelegramClient

api_id = 611335
api_hash = 'd524b414d21f4d37f08684c1df41ac9c'
phone = '+959663617728'
session_name = 'discoverer_session'

async def main():
    try:
        # 只尝试读取现有的 session，如果不登录会提示
        client = TelegramClient(session_name, api_id, api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            print("==================================================")
            print("❌ 当前未登录任何账号！")
            print("请先运行爬虫程序并输入手机号/验证码登录。")
            print("==================================================")
            return

        me = await client.get_me()
        
        print("==================================================")
        print("✅ 当前已登录账号信息：")
        print("==================================================")
        print(f"👤 账号名称: {me.first_name} {me.last_name or ''}")
        print(f"🆔 Username: @{me.username if me.username else '未设置'}")
        print(f"📱 手机号码: +{me.phone if me.phone else '未知'}")
        print(f"🔢 账号 ID : {me.id}")
        print("==================================================")
        print("如果你想换账号，请运行【清理数据.bat】或者手动删除 discoverer_session.session 文件。")
        
    except Exception as e:
        print(f"读取账号信息失败: {e}")
    finally:
        await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
