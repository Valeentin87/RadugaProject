
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import emoji


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize('Заявки'), callback_data='claims')],
         [InlineKeyboardButton(text=emoji.emojize('О боте'), callback_data='info')]
        ]
    )





