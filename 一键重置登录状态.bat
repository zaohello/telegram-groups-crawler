@echo off
chcp 65001 >nul
echo 正在注销当前账号...
echo 注意：此操作将删除当前 Telegram 登录状态。
echo.

del /f /q discoverer_session.session
del /f /q discoverer_session.session-journal

echo 清理完成！
echo 下次运行【一键启动爬虫.bat】时，将提示您输入新的手机号进行登录。
echo.
pause
