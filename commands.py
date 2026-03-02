from aiogram.types import BotCommand

# Основные команды (для всех пользователей)
BASIC_COMMANDS = [
    BotCommand(command="start", description="Начать работу"),
]

# Команды администратора
ADMIN_COMMANDS = [
    BotCommand(command="admin", description="Панель администратора"),
]