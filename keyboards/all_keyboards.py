
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import emoji


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize(':man_mechanic:Заявки'), callback_data='claims')],
         [InlineKeyboardButton(text=emoji.emojize(':information:О боте'), callback_data='info')]
        ]
    )


def claim_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize(':bell:Проверить новые'), callback_data='new_claims')],
         [InlineKeyboardButton(text=emoji.emojize(':recycling_symbol:Изменен статус'), callback_data='change_status')],
         [InlineKeyboardButton(text=emoji.emojize(':double_exclamation_mark:Превышен срок'), callback_data='dedline_exceed')]
         #[InlineKeyboardButton(text=emoji.emojize('Закрыты'), callback_data='claim_closed')]
        ]
    )




