from copy import deepcopy
from datetime import datetime, timedelta
import calendar
from typing import List, Optional, Tuple
import emoji
from decouple import config
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from create_bot import logger
from data.metro_data import metro_map, stations_by_rayon, dictionary_areas, dictionary_of_correspondences
from db_handler.base import get_info_of_establishments
from utils.save_read_csv import save_statistic_to_csv



