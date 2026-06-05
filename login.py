import asyncio
from telethon import TelegramClient

api_id = 611335
api_hash = 'd524b414d21f4d37f08684c1df41ac9c'
session_name = 'discoverer_session'

async def main():
    print("==================================================")
    print("Telegram 账号登录程序")
    print("==================================================")
    
    client = TelegramClient(session_name, api_id, api_hash)
    
    # client.start() 在没有 session 时会自动在终端提示输入手机号和验证码
    await client.start()
    
    me = await client.get_me()
    print("\n✅ 登录成功！")
    print("==================================================")
    print(f"👤 账号名称: {me.first_name} {me.last_name or ''}")
    print(f"📱 手机号码: +{me.phone if me.phone else '未知'}")
    print("==================================================")
    print("现在您可以关闭此窗口，并运行【一键启动爬虫.bat】了！")
    
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
