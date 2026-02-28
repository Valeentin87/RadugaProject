
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import emoji


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize('Заявки'), callback_data='claims')],
         [InlineKeyboardButton(text=emoji.emojize('О боте'), callback_data='info')]
        ]
    )


def claim_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize('Проверить новые'), callback_data='new_claims')],
         [InlineKeyboardButton(text=emoji.emojize('Изменен статус'), callback_data='change_status')],
         [InlineKeyboardButton(text=emoji.emojize('Превышен срок'), callback_data='dedline_exceed')],
         [InlineKeyboardButton(text=emoji.emojize('Закрыты'), callback_data='claim_closed')]
        ]
    )




