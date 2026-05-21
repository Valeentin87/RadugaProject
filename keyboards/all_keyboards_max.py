from aiomax.buttons import CallbackButton, MessageButton, KeyboardBuilder
import emoji

    
def start_keyboard_max():
    start_kb = KeyboardBuilder()
    start_kb.row(CallbackButton(text=emoji.emojize(':man_mechanic:Заявки'), payload="claims"))
    start_kb.row(CallbackButton(text=emoji.emojize(':information:О боте'), payload="info"))
    
    return start_kb.to_list()


def claim_keyboard_max():
    claims_kb = KeyboardBuilder()
    claims_kb.row(CallbackButton(text=emoji.emojize(':bell:Проверить новые'), payload="new_claims"))
    claims_kb.row(CallbackButton(text=emoji.emojize(':recycling_symbol:Изменен статус'), payload="change_status"))
    claims_kb.row(CallbackButton(text=emoji.emojize(':double_exclamation_mark:Превышен срок'), payload="dedline_exceed"))
    
    return claims_kb.to_list()