import os, sys

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common import NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
import logging
import time
from copy import deepcopy
import json
import random
from create_bot import logger
from db_handler.base import add_new_claim, add_new_claims

# # Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s [%(levelname)s] %(message)s',
#     handlers=[
#         logging.FileHandler('scrap_util.log', encoding='utf-8'),
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger(__name__)

def create_chrome_options():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    options.add_argument("--accept-language=ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7")
    # Включаем логирование браузера
    options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    return options

def create_driver():
    """Создаёт экземпляр драйвера с автоматическим управлением ChromeDriver"""
    try:
        service = Service(ChromeDriverManager().install())
        options = create_chrome_options()
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("ChromeDriver успешно инициализирован")
        return driver
    except Exception as e:
        logger.error(f"Ошибка при создании драйвера: {e}")
        raise

def save_page_html(driver, filename, directory="."):
    """Сохраняет HTML-код текущей страницы"""
    try:
        filepath = os.path.join(directory, filename)
        os.makedirs(directory, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info(f"HTML сохранён: {filepath}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении {filepath}: {e}")


def click_with_retries(element, driver, max_retries=3):
    """Кликает по элементу с повторными попытками и явными ожиданиями"""
    for attempt in range(max_retries):
        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(element))
            element.click()
            logger.info(f"Клик успешен (попытка {attempt + 1})")
            return True
        except ElementClickInterceptedException as e:
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}. Ждём 5 сек и пробуем снова.")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при клике: {e}")
            return False
    return False

def get_browser_logs(driver):
    """Собирает логи браузера (JS‑ошибки)"""
    try:
        logs = driver.get_log("browser")
        for log in logs:
            if log["level"] == "SEVERE":
                logger.error(f"JS‑ошибка: {log['message']}")
                if "403" in log["message"]:
                    logger.warning("Обнаружена ошибка 403 — возможно, проблема с авторизацией или правами доступа")
    except:
        logger.warning("Не удалось получить логи браузера.")

def remove_overlay(driver):
    """Принудительно удаляет оверлей, если он есть"""
    try:
        overlay = driver.find_element(By.CSS_SELECTOR, "div.cdk-overlay-backdrop")
        driver.execute_script("arguments[0].remove();", overlay)
        logger.info("Оверлей удалён из DOM через JS.")
        return True
    except:
        logger.info("Оверлея не найдено в DOM — продолжаем.")
        return False

def check_authorization_status(driver):
    """Комплексная проверка успешности авторизации"""
    current_url = driver.current_url
    page_title = driver.title

    # Проверка URL
    if "/claims" in current_url:
        logger.info("URL подтверждает авторизацию: {current_url}")

    # Проверка заголовка
    if "Решаем проблемы вместе" in page_title:
        logger.info("Заголовок подтверждает авторизацию: {page_title}")

    # Поиск ключевых элементов авторизованной зоны
    auth_elements = [
        (By.CSS_SELECTOR, ".user-profile"),
        (By.XPATH, "//span[contains(text(), 'Добро пожаловать')]"),
        (By.ID, "user-menu"),
        (By.XPATH, "//div[contains(@class, 'cup') and .//div[text()='Новые:']]")
    ]

    for locator in auth_elements:
        try:
            element = WebDriverWait(driver, 5).until(EC.presence_of_element_located(locator))
            logger.info(f"Найден элемент авторизации: {locator}")
            return True
        except TimeoutException:
            continue

    logger.warning("Не удалось подтвердить авторизацию стандартными способами")
    return False



def click_new_claims_by_icon(driver, wait):
    """
    Пытается найти и кликнуть по элементу с иконкой plus.svg (новые заявки).
    Возвращает: bool — True при успехе, False при провале всех попыток.
    """
    logger.info("Поиск элемента «НОВЫЕ» по иконке plus.svg...")

    search_strategies = [
        {
            'type': 'xpath',
            'locator': "//div[_ngcontent-ng-c3750005855][contains(@class, 'cup')]//img[@src='assets/images/statistic/plus.svg']/ancestor::div[1]",
            'description': 'XPath: родительский div с классом cup и Angular-атрибутом, содержащий img[src=plus.svg]'
        },
        {
            'type': 'css',
            'locator': "div[_ngcontent-ng-c3750005855].d-flex.align-center.cup:has(img[src='assets/images/statistic/plus.svg'])",
            'description': 'CSS: div с Angular-атрибутом и классами, содержащий img с src=plus.svg'
        },
        {
            'type': 'xpath',
            'locator': "//div[_ngcontent-ng-c3750005855 and contains(@class, 'd-flex') and contains(@class, 'align-center') and contains(@class, 'cup')]",
            'description': 'XPath: div с полным набором классов и Angular-атрибутом'
        },
        {
            'type': 'css',
            'locator': "div[_ngcontent-ng-c3750005855][position='top'].d-flex.cup",
            'description': 'CSS: комбинация Angular-атрибута, атрибута position и классов'
        },
        {
            'type': 'xpath',
            'locator': "//div[contains(text(), 'Новые:')]/ancestor::div[contains(@class, 'd-flex')][1]",
            'description': 'XPath: поиск по тексту «Новые:» и родительскому контейнеру'
        }
    ]

    for i, strategy in enumerate(search_strategies, 1):
        try:
            logger.info(f"Попытка {i}: {strategy['description']}")

            if strategy['type'] == 'xpath':
                element = wait.until(
                    EC.element_to_be_clickable((By.XPATH, strategy['locator']))
                )
            else:  # css
                element = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, strategy['locator']))
                )

            # Проверка видимости и возможности клика
            if not element.is_displayed():
                logger.warning(f"Элемент найден, но не виден: {strategy['description']}")
                continue

            if not element.is_enabled():
                logger.warning(f"Элемент найден, но недоступен для клика: {strategy['description']}")
                continue

            # Прокрутка к элементу
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                element
            )
            time.sleep(0.5)

            # Дополнительный клик через JavaScript на случай проблем с обычным кликом
            try:
                element.click()
            except Exception:
                logger.warning("Обычный клик не сработал, пробуем через JavaScript")
                driver.execute_script("arguments[0].click();", element)

            logger.info(f"✅ Элемент найден и клик выполнен (стратегия {i})")
            return True

        except TimeoutException:
            logger.debug(f"Стратегия {i} не сработала: таймаут ожидания элемента")
            continue
        except NoSuchElementException:
            logger.debug(f"Стратегия {i} не сработала: элемент не найден")
            continue
        except Exception as e:
            logger.warning(f"Ошибка в стратегии {i} ({strategy['description']}): {e}")
            continue

    # Финальная диагностика
    try:
        # Поиск всех img с plus.svg
        all_imgs = driver.find_elements(By.XPATH, "//img[contains(@src, 'plus.svg')]")
        logger.debug(f"Найдено img с 'plus.svg': {len(all_imgs)}")

        for idx, img in enumerate(all_imgs):
            try:
                parent = img.find_element(By.XPATH, "./ancestor::div[contains(@class, 'd-flex')][1]")
                classes = parent.get_attribute('class')
                ng_content = parent.get_attribute('_ngcontent-ng-c3750005855')
                logger.debug(f"  Img {idx}: родительский класс='{classes}', _ngcontent='{ng_content}'")
            except Exception as e:
                logger.debug(f"  Не удалось получить информацию о родителе img {idx}: {e}")

        # Проверка наличия Angular-атрибутов на странице
        angular_elements = driver.find_elements(
            By.XPATH,
            "//*[starts-with(name(), '_ngcontent')]"
        )
        logger.debug(f"На странице найдено Angular-элементов: {len(angular_elements)}")

    except Exception as e:
        logger.warning(f"Не удалось выполнить диагностику: {e}")

    logger.error("❌ Не удалось найти и кликнуть по элементу ни одной стратегией")
    return False


def collect_new_claims_data(driver):
    """
    Собирает информацию по новым заявкам со страницы.

    Ищет внутри <tbody role="rowgroup"> все строки <tr role="row">,
    извлекает данные по заявкам и возвращает словарь.

    Возвращает:
        dict: {
            "6180019": {
                "Дата обращения": "23 февраля 2026 14:21",
                "Категория": "Привести параметры температуры горячей воды в квартире в соответствие с нормативным значением",
                "Адрес": "Видное г, Зеленые аллеи б-р, 11",
                "Срочность": "Плановая",
                "Срок": "24 февраля 2026 14:22"
            },
            ...
        }
    """
    # Находим tbody с role="rowgroup"
    tbody = driver.find_element(By.XPATH, "//tbody[@role='rowgroup']")

    # Находим все строки tr с role="row" внутри tbody
    rows = tbody.find_elements(By.XPATH, ".//tr[@role='row']")

    claims_data = {}

    for row in rows:
        # Извлекаем номер заявки (из первого td > span)
        try:
            id_element = row.find_element(
                By.XPATH,
                ".//td[contains(@class, 'cdk-column-id')]//span"
            )
            claim_id = id_element.text.strip()
        except Exception:
            claim_id = "N/A"

        # Дата обращения (второй td > span)
        try:
            date_element = row.find_element(
                By.XPATH,
                ".//td[contains(@class, 'cdk-column-created')]//span"
            )
            date_text = date_element.text.strip()
        except Exception:
            date_text = "N/A"

        # Категория (третий td > span)
        try:
            category_element = row.find_element(
                By.XPATH,
                ".//td[contains(@class, 'cdk-column-category-name')]//span"
            )
            category_text = category_element.text.strip()
        except Exception:
            category_text = "N/A"

        # Адрес (четвёртый td > span)
        try:
            address_element = row.find_element(
                By.XPATH,
                ".//td[contains(@class, 'cdk-column-address-address')]//span"
            )
            address_text = address_element.text.strip()
        except Exception:
            address_text = "N/A"

        # Срочность (пятый td > div > span)
        try:
            urgency_element = row.find_element(
                By.XPATH,
                ".//td[contains(@class, 'cdk-column-type-description')]//div[@class='claim-type']//span"
            )
            urgency_text = urgency_element.text.strip()
        except Exception:
            urgency_text = "N/A"

        # Срок (шестой td > span)
        try:
            deadline_element = row.find_element(
                By.XPATH,
                ".//td[contains(@class, 'cdk-column-deadline')]//span"
            )
            deadline_text = deadline_element.text.strip()
        except Exception:
            deadline_text = "N/A"

        # Добавляем данные в словарь
        claims_data[claim_id] = {
            "appeal_date": date_text,
            "description": category_text,
            "address": address_text,
            "urgency": urgency_text,
            "due_date": deadline_text
        }

    return claims_data

# Пример использования:
# driver = webdriver.Chrome(options=create_chrome_options())
# driver.get("ваш_url")
# data = collect_new_claims_data(driver)
# print(data)


def close_popup_if_exists(driver, wait_timeout=10):
    """
    Ищет на текущей странице кликабельный элемент с классом 'popup__close' и нажимает на него
    для закрытия всплывающего окна.

    Args:
        driver: экземпляр WebDriver
        wait_timeout: время ожидания элемента в секундах (по умолчанию 10 с)

    Returns:
        bool: True, если элемент найден и клик выполнен; False, если элемент не найден
    """
    logger.info("close_popup_if_exists: стартовал")
    wait = WebDriverWait(driver, wait_timeout)

    try:
        # Ожидаем появления кликабельного элемента с классом popup__close
        close_button = wait.until(
            EC.element_to_be_clickable((By.CLASS_NAME, "popup__close"))
        )

        # Прокручиваем к элементу, чтобы он был виден на экране
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
            close_button
        )

        # Кликаем по элементу
        close_button.click()
        logger.info("Всплывающее окно успешно закрыто (кнопка с классом 'popup__close')")
        logger.info("close_popup_if_exists: успешно финишировал")
        return True

    except Exception as e:
        logger.warning(f"Элемент с классом 'popup__close' не найден или не кликабелен: {e}")
        return False


def click_work_button(driver, wait_timeout=10):
    """
        Ищет на текущей странице кликабельный элемент — кнопку «В работу» с заданными атрибутами
        и нажимает на неё.
        Args:
        driver: экземпляр WebDriver
           wait_timeout: время ожидания элемента в секундах (по умолчанию 10 с)

        Returns:
           bool: True, если элемент найден и клик выполнен; False, если элемент не найден
    """
    print("click_work_button: Стартовал метод поиска кнопки В РАБОТУ")

    wait = WebDriverWait(driver, wait_timeout)
    button = None

    try:
        # Стратегия 1: поиск по классу кнопки и тексту внутри span
        print("Стратегия 1: поиск по классу 'lib-button green' и тексту ' В работу '")
        button = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[@class='lib-button green' and .//span[text()=' В работу ']"
            )))
    except Exception as e1:
        print(f"Стратегия 1 не сработала: {e1}")
        try:
            # Стратегия 2: поиск по роли и классу кнопки (более общий)
            print("Стратегия 2: поиск по role='button' и классу 'lib-button'")
            button = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[@class='lib-button green']//span[contains(text(), 'В работу')]"
                )))
        except Exception as e2:
            print(f"Стратегия 2 не сработала: {e2}")
            try:
                # Стратегия 3: поиск по тексту внутри кнопки (игнорируя структуру)
                print("Стратегия 3: поиск по содержанию текста 'В работу' в span")
                button = wait.until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[.//span[contains(text(), 'В работу')]]"
                    )))
            except Exception as e3:
                print(f"Стратегия 3 не сработала: {e3}")
                try:
                  # Стратегия 4: поиск по комбинации атрибутов
                    print("Стратегия 4: поиск по комбинации role, type, class, tabindex")
                    button = wait.until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            "//button[@role='button' and @type='button' and contains(@class, 'lib-button') and @tabindex='0']"
                        )))
                except Exception as e4:
                    print(f"Стратегия 4 не сработала: {e4}")
                    try:
                        # Дополнительная стратегия: поиск любого кликабельного элемента с текстом «В работу»
                        print("Дополнительная стратегия: поиск любого кликабельного элемента с текстом 'В работу'")
                        button = wait.until(
                        EC.element_to_be_clickable((
                            By.XPATH,
                            "//*[contains(text(), 'В работу') and (self::button or ancestor::button)]"
                        )))
                    except Exception as e5:
                        print(f"Дополнительная стратегия не сработала: {e5}")
                        logger.warning("Не удалось найти кнопку «В работу» ни по одному из селекторов")
                        return False

    if button is not None:
        # Прокручиваем к элементу, чтобы он был виден на экране
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
            button
        )
        print("Элемент найден, прокручиваемся к нему")

        # Пытаемся кликнуть стандартным способом
        try:
            button.click()
            logger.info("Кнопка «В работу» успешно нажата (стандартный клик)")
            print("Кнопка «В работу» успешно нажата (стандартный клик)")
            return True
        except Exception:
        # Если стандартный клик не сработал, используем JavaScript‑клик
            try:
                driver.execute_script("arguments[0].click();", button)
                logger.info("Кнопка «В работу» успешно нажата (JavaScript‑клик)")
                print("Кнопка «В работу» успешно нажата (JavaScript‑клик)")
                return True
            except Exception as e:
                logger.error(f"Не удалось нажать кнопку «В работу»: {e}")
                print(f"Не удалось нажать кнопку «В работу»: {e}")
                return False
    else:
        logger.warning("Кнопка «В работу» не найдена")
        print("Кнопка «В работу» не найдена после всех стратегий поиска")
        return False


def wait_for_page_load(driver, timeout=30):
    """Ждёт полной загрузки страницы"""
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )
    time.sleep(1)  # Небольшая пауза для стабилизации

# ------- логика поиска кликабельных элементов для нажатия на НОВАЯ ЗАЯВКА и получения более подробной информации по ней с целью последующего принятия в работу -------


def click_all_claim_details_and_save(driver, wait_timeout=10):
    """
        Ищет элементы с классом 'claim-status', находит кликабельные элементы рядом с ними,
        кликает на каждый и сохраняет информацию о страницах с деталями заявок.
    """
    wait = WebDriverWait(driver, wait_timeout)
    all_claims_info = []
    try:
        # Ждём появления элементов с классом claim-status
        status_elements = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "claim-status"))
        )
        if not status_elements:
            print("Не найдено элементов с классом 'claim-status'")
            return all_claims_info
        print(f"Найдено элементов с классом 'claim-status': {len(status_elements)}")
        # Сохраняем базовый URL для навигации
        base_url = driver.current_url
        print(f"{base_url=}")
        for i in range(len(status_elements)):
            print(f"\n--- Обработка элемента #{i + 1} из {len(status_elements)} ---")
            claim_info = None
            clicked = False
            # Перезагружаем страницу перед обработкой каждого элемента
            # driver.get(base_url)
            # wait.until(EC.url_contains(base_url))
            time.sleep(2)
            # Снова находим все элементы claim-status после перезагрузки
            status_elements_refreshed = wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "claim-status"))
            )
            if i >= len(status_elements_refreshed):
                print(f"Элемент #{i + 1} больше не найден после перезагрузки страницы")
                continue
            current_status_element = status_elements_refreshed[i]
            # Получаем строку таблицы, содержащую текущий элемент claim-status
            try:
                row_element = current_status_element.find_element(By.XPATH, "./ancestor::tr[@role='row']")
                row_index = row_element.get_attribute("data-index") or str(i)
            except Exception:
                print("Не удалось найти строку таблицы для текущего элемента claim-status")
                continue
            strategies = [
                # 1. Сама строка таблицы
                {
                   'locator': f"//tr[@role='row'][{i + 1}]",
                   'type': By.XPATH,
                   'desc': 'Сама строка таблицы (tr[role="row"])'
                },
                # 2. Номер заявки в текущей строке
                {
                    'locator': f"//tr[@role='row'][{i + 1}]//td[contains(@class, 'cdk-column-id')]//span",
                    'type': By.XPATH,
                    'desc': 'Номер заявки в текущей строке'
                },
                # 3. Статус в текущей строке
                {
                    'locator': f"//tr[@role='row'][{i + 1}]//span[@class='claim-status-name']",
                    'type': By.XPATH,
                    'desc': 'Статус заявки в текущей строке'
                }
            ]
            for strategy in strategies:
                try:
                    print(f"Пробуем стратегию: {strategy['desc']}")
                    clickable_element = wait.until(
                        EC.element_to_be_clickable((strategy['type'], strategy['locator']))
                    )
                    # Прокрутка к элементу
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                        clickable_element
                    )
                    time.sleep(0.5)
                    # Пытаемся кликнуть
                    try:
                        clickable_element.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", clickable_element)
                    # Ждём загрузки деталей заявки
                    time.sleep(2)
                    # Сохраняем информацию о текущей странице
                    claim_info = save_claim_details(driver, claim_id=f"claim_{i + 1}")
                    if claim_info:
                        print("Информация о заявке успешно сохранена")
                        claim_info['claim_number'] = i + 1
                        all_claims_info.append(claim_info)
                        clicked = True
                        # Принимаем заявку в работу - пока без реализации
                        click_result = click_work_button(driver)
                        print("Получилось нажать кнопку ПРИНЯТЬ В РАБОТУ, сохраняем контент страницы")
                        if click_result:
                            time.sleep(2.5)
                            save_claim_details(driver, approve_flag=True)
                        # Закрываем окно
                        close_popup_if_exists(driver)
                        break
                    else:
                        print("Не удалось сохранить информацию о заявке")
                except TimeoutException:
                    print(f"Элемент не найден/не кликабелен: {strategy['desc']}")
                    continue
                except Exception as e:
                    print(f"Ошибка при клике по {strategy['desc']}: {e}")
                    continue
            if not clicked:
                print(f"Не удалось обработать элемент #{i + 1} — переходим к следующему")
        print(f"\n--- Завершено: обработано {len(all_claims_info)} заявок из {len(status_elements)} ---")
        return all_claims_info
    except Exception as e:
        print(f"Критическая ошибка при обработке элементов claim-status: {e}")
        return all_claims_info


def get_info_of_table_with_claims(driver, wait_timeout=10):
    """
        Ищет элементы с классом 'claim-status' - все строки таблицы с заявками и сохраняем последние 10 из них.
    """
    wait = WebDriverWait(driver, wait_timeout)
    all_claims_by_row = []
    try:
        # Ждём появления элементов с классом claim-status
        status_elements = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "claim-status"))
        )
        if not status_elements:
            print("Не найдено элементов с классом 'claim-status'")
            return all_claims_by_row
        print(f"Найдено элементов с классом 'claim-status': {len(status_elements)}")

        # приступаем к поиску элементов с аттрибутом role ='row'
        try:
            row_elements = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "cdk-row"))
            )
            print(f"Найдено элементов с классом class='cdk-row': {len(row_elements)}")
        except Exception:
            print("Не удалось найти строки таблицы с классом class='cdk-row'")
            return all_claims_by_row
        
        if len(status_elements) == len(row_elements):
            print("Количество строк таблицы равно количеству заявок")

        if len(row_elements) >= -10:
            for element in row_elements[-10:]:
                all_claims_by_row.append(element.get_attribute("outerHTML"))
        else:
            for element in row_elements:
                all_claims_by_row.append(element.get_attribute("outerHTML"))
        
        print(f"Информация по первому элементу-строке:\n{all_claims_by_row[0]}")
        return all_claims_by_row
    
    except Exception as e:
        print(f"get_info_of_table_with_claims: При получении информации о строках таблицы с заявками произошла ошибка  {e}")


def parse_claim_from_html(html_string):
    """
    Извлекает информацию о заявке из HTML-строки.

    Args:
        html_string (str): HTML-код строки таблицы с заявкой

    Returns:
        dict: Словарь с полями заявки
    """
    soup = BeautifulSoup(html_string, 'html.parser')

    # Находим все ячейки <td> в строке
    cells = soup.find_all('td')

    # Извлекаем данные из каждой ячейки по порядку
    claim_id = cells[0].get_text(strip=True) if len(cells) > 0 else ""
    appeal_date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
    description = cells[2].get_text(strip=True) if len(cells) > 2 else ""
    address = cells[3].get_text(strip=True) if len(cells) > 3 else ""

    # Для срочности (urgency) — ищем внутри ячейки с типом заявки
    urgency = ""
    if len(cells) > 4:
        urgency_span = cells[4].find('span')
        if urgency_span:
            urgency = urgency_span.get_text(strip=True)

    due_date = cells[5].get_text(strip=True) if len(cells) > 5 else ""

    # Для статуса (status) — ищем внутри ячейки со статусом
    status = ""
    if len(cells) > 6:
        status_span = cells[6].find('span', class_='claim-status-name')
        if status_span:
            status = status_span.get_text(strip=True)

    return {
        "claim_id": claim_id,
        "company_name": "",  # В HTML нет данных о компании
        "appeal_date": appeal_date,
        "description": description,
        "address": address,
        "urgency": urgency,
        "due_date": due_date,
        "status": status
    }



def save_claim_details(driver, claim_id="unknown", approve_flag=False):
    """
        Сохраняет информацию о детализированной странице заявки.
        Добавляет ID заявки в имя файла для уникальности.
    """
    try:
        page_url = driver.current_url
        logger.info(f"save_claim_details: {page_url=}")
        claim_id:str = page_url.split('/')[-1]
        if not claim_id.isdigit():
            return None
        page_source = driver.page_source
        # Сохраняем HTML-код страницы
        filename = ''
        if not approve_flag:
            filename = f"work_parsed_pages/claim_detail_{claim_id}.html"
        else:
            filename = f"work_parsed_pages/claim_approve_{claim_id}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(page_source)
        logging.info(f"HTML сохранён: {filename}")
        # Ищем заголовок или ключевые данные на странице деталей
        try:
            title_element = driver.find_element(
                By.XPATH,
                "//h1 | //h2 | //*[contains(@class, 'title') | contains(@class, 'header')]"
            )
            title = title_element.text.strip()
        except Exception:
            title = "Заголовок не найден"
        claim_info = {
            "url": page_url,
            "title": title,
            "html_file": filename,
            "timestamp": int(time.time())
        }
        return claim_info
    except Exception as e:
        print(f"Ошибка при сохранении деталей заявки: {e}")
        return None


# def save_claim_details(driver):
#     """
#     Сохраняет информацию о детализированной странице заявки.

#     Returns:
#         dict с информацией о заявке или None
#     """
#     try:
#         page_url = driver.current_url
#         claim_id = page_url.split('/')[-1]
#         save_page_html(driver, f'claim_detail_{claim_id}.html', 'work_parsed_pages')

#         # Ищем заголовок или ключевые данные на странице деталей
#         try:
#             title_element = driver.find_element(
#                 By.XPATH,
#                 "//h1 | //h2 | //*[contains(@class, 'title') | contains(@class, 'header')]"
#             )
#             title = title_element.text.strip()
#         except Exception:
#             title = "Заголовок не найден"

#         # Сохраняем скриншот для визуальной верификации
#         timestamp = int(time.time())
#         screenshot_path = f"claim_details_{timestamp}.png"
#         driver.save_screenshot(screenshot_path)

#         claim_info = {
#             "url": page_url,
#             "title": title,
#             "screenshot": screenshot_path,
#             "timestamp": timestamp
#         }
#         return claim_info
#     except Exception as e:
#         print(f"Ошибка при сохранении деталей заявки: {e}")
#         return None


def find_clickable_nearby(driver, status_element):
    """
    Ищет кликабельный элемент поблизости от элемента status_element.

    Проверяет:
    1. Родительские элементы.
    2. Соседние элементы (предыдущий/следующий sibling).
    3. Потомок с классом 'claim-status-name' или похожий.

    Returns:
        WebElement или None
    """
    strategies = [
        # 1. Родительский элемент (часто кликабелен)
        lambda: status_element.find_element(By.XPATH, "./ancestor::*"),
        # 2. Ближайший кликабельный родитель
        lambda: driver.execute_script(
            "let el = arguments[0]; while (el && !el.click) { el = el.parentElement; } return el;",
            status_element
        ),
        # 3. Соседний элемент с классом, содержащим 'click', 'btn', 'link'
        lambda: status_element.find_element(
            By.XPATH,
            "./following-sibling::* | ./preceding-sibling::*[contains(@class, 'click') or contains(@class, 'btn') or contains(@class, 'link')]"
        ),
        # 4. Потомок с текстом 'Новая заявка'
        lambda: status_element.find_element(
            By.XPATH,
            ".//*[contains(text(), 'Новая заявка')]"
        ),
        # 5. Потомок с классом claim-status-name
        lambda: status_element.find_element(
            By.XPATH,
            ".//span[@class='claim-status-name']"
        ),
        # 6. Любой кликабельный потомок
        lambda: status_element.find_element(
            By.XPATH,
            ".//*[@onclick or @href or contains(@class, 'clickable')]"
        )
    ]

    for i, strategy in enumerate(strategies):
        try:
            element = strategy()
            if element and is_element_clickable(element):
                return element
        except Exception:
            continue

    return None


def is_element_clickable(element):
    """Проверяет, можно ли кликнуть по элементу."""
    return (
        element.is_displayed() and
        element.is_enabled() and
        element.size['width'] > 0 and
        element.size['height'] > 0
    )


def scroll_to_bottom(driver, max_scrolls=5, delay=1):
    """Многократно скроллит до низа с задержкой между скроллами"""
    last_height = driver.execute_script("return document.body.scrollHeight")

    for i in range(max_scrolls):
        # Скроллим до низа
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        print(f"Скролл #{i+1} до низа выполнен")

        # Ждём загрузки нового контента
        time.sleep(delay)

        # Получаем новую высоту страницы
        new_height = driver.execute_script("return document.body.scrollHeight")

        # Если высота не изменилась — достигли конца
        if new_height == last_height:
            print("Достигнут конец страницы")
            break

        last_height = new_height


def scroll_and_click_show_more(driver, max_attempts=300, wait_timeout=10):
    """
        Скроллит страницу вниз, ищет кнопку «Показать еще» и нажимает на неё до тех пор,
        пока кнопка не перестанет быть доступной.

        Args:
            driver: экземпляр WebDriver
            max_attempts: максимальное количество попыток (защита от бесконечного цикла)
            wait_timeout: время ожидания элемента в секундах

        Returns:
            int: количество успешно выполненных кликов по кнопке «Показать еще»
    """
    click_count = 0
    attempt = 1

    html_info_of_all_claims = []

    #iter_claims_info = get_info_of_table_with_claims(driver)

    #html_info_of_all_claims.extend(deepcopy(iter_claims_info))

    print("scroll_and_click_show_more: Старт поиска и нажатия кнопки «Показать еще»")
    while attempt <= max_attempts:
        print(f"\n--- Попытка #{attempt} из {max_attempts} ---")

        # Скроллим в самый низ страницы
        #driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        scroll_to_bottom(driver)
        print("Страница прокручена в самый низ")
        time.sleep(3)  # ждём 3 секунды
        print("Подождали 2 секунды после скролла для загрузки контента")

        
        current_iter_claims_info = get_info_of_table_with_claims(driver)
        html_info_of_all_claims.extend(deepcopy(current_iter_claims_info))

        wait = WebDriverWait(driver, wait_timeout)
        button = None

        try:
            # Поиск кнопки по тексту внутри span
            button = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button//span[contains(text(), 'Показать еще')]/ancestor::button"
                )))

            print("Кнопка «Показать еще» найдена, выполняется клик")

            # Прокрутка к элементу для надёжности
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                button
            )

            # Кликаем по кнопке
            try:
                button.click()
                logger.info(f"Кнопка «Показать еще» успешно нажата (клик #{click_count + 1})")
                print(f"Кнопка «Показать еще» успешно нажата (клик #{click_count + 1})")

                # Увеличиваем счётчик кликов
                click_count += 1

                # Ждём случайное время от 5 до 10 секунд
                wait_time = random.uniform(5, 10)
                print(f"Ожидание {wait_time:.1f} секунд перед следующей попыткой")
                time.sleep(wait_time)

                # Обновляем страницу или ждём загрузки нового контента
                # (можно добавить проверку загрузки контента при необходимости)

            except Exception as click_error:
                logger.warning(f"Не удалось нажать кнопку «Показать еще»: {click_error}")
                print(f"Ошибка при клике: {click_error}")
                break  # Выходим из цикла при ошибке клика

        except Exception as e:
            # Элемент не найден — это ожидаемое завершение цикла
            if "TimeoutException" in str(type(e)) or "NoSuchElementException" in str(type(e)):
                print("Кнопка «Показать еще» больше не найдена — достигнут конец списка")
                break
            else:
                # Другие ошибки — продолжаем попытки
                print(f"Неожиданная ошибка при поиске кнопки: {e}")
                attempt += 1
                continue
        finally:        
            attempt += 1

            # Дополнительная проверка: если после клика кнопка всё ещё видна, продолжаем
            # В противном случае — завершаем цикл
            if button and not button.is_displayed():
                print("Кнопка больше не отображается после клика — завершаем работу")
                break

    print(f"\n--- Завершено: выполнено {click_count} кликов по кнопке «Показать еще» ---")
    print(f"Собрана информация о  {len(html_info_of_all_claims)} заявках")
    return click_count, html_info_of_all_claims



# ------ ниже тестовая main ---------------

# login="5003108379"
# password="pVK8Wtx7"

COMPANY_ACCESS = os.getenv('COMPANY_ACCESS')
company_access = json.loads(COMPANY_ACCESS)
# company_name = ''
# for key, value in company_access.items():
#     if value[1] == login:
#         company_name = value[0]



def scroll_and_click_login_link(driver, timeout=60):
    """
    Гарантированно скроллит страницу наверх, ищет и нажимает на элемент с классом
    header-login__link и текстом «Войти».

    Args:
        driver: экземпляр WebDriver
        timeout: время ожидания элемента в секундах

    Returns:
        bool: True, если элемент найден и нажата кнопка, False — в случае ошибки
    """
    try:
        # 1. Гарантированный скролл наверх
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)  # небольшая пауза после скролла

        # 2. Ожидание появления кликабельного элемента
        wait = WebDriverWait(driver, timeout)
        element = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[@class='header-login__link' and contains(text(), 'Войти')]"
            ))
        )

        # 3. Дополнительная проверка видимости и возможности клика
        if element.is_displayed() and element.is_enabled():
            # 4. Попытка нажать (с обработкой возможных ошибок)
            try:
                element.click()
                print("✅ Элемент «Войти» успешно найден и нажата кнопка")
                return True
            except ElementClickInterceptedException:
                # Если элемент перекрыт, используем JS‑клик
                driver.execute_script("arguments[0].click();", element)
                print("✅ Элемент «Войти» нажата через JavaScript")
                return True
        else:
            print("❌ Элемент найден, но не кликаем/не виден")
            return False

    except TimeoutException:
        print("❌ Элемент с текстом «Войти» не найден за отведённое время")
        return False
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        return False




async def filled_claims_to_base(login:str, password:str, company_name:str):
    """Отвечает за наполнение базы данных информацией обо всех имеющихся заявказ
    по всем управляющим компаниям"""
    claims_row_info = None
    logger.info(f"Приступили к обновлению базы данных по всем заявкам для УК {company_name}")
    print(f"Приступили к обновлению базы данных по всем заявкам для УК {company_name}")

    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 30)

        # 1. Загрузка страницы
        driver.get("https://eds.mosreg.ru/")
        logger.info(f"Страница загружена: {driver.current_url}")
        save_page_html(driver, 'login_page.html', 'work_parsed_pages')

        
        scroll_and_click_login_link(driver)
        
        # 2. Удаление оверлея
        remove_overlay(driver)

        # 3. Поиск контейнера формы
        logger.info("Ожидание видимости контейнера формы...")
        form_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.login-form'))
        )
        if form_container:
            logger.info("Контейнер формы найден - выделяем его...")
            driver.execute_script("arguments[0].style.border='3px solid red'", form_container)

        # 4. Поле email
        logger.info("Поиск поля email...")
        email_field = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'dd-lib-input[formcontrolname="login-form-email"] input'
            ))
        )
        if email_field:
            logger.info("Поле email найдено - выделяем его...")
            driver.execute_script("arguments[0].style.background='yellow'", email_field)
        email_field.clear()
        email_field.send_keys(login)
        print("Email введен")
        logger.info(f"Email введён: {email_field.get_attribute('value')}")

        # 5. Поле пароля
        password_field = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@placeholder='Пароль' and @type='password']"
            ))
        )
        logger.info("Поле пароля найдено")
        password_field.clear()
        
        password_field.send_keys(password)
        print("Пароль введен введен")
        logger.info(f"Пароль введён: {len(password_field.get_attribute('value'))} символов")

        # 6. Кнопка «Авторизоваться»
        submit_button = wait.until(
    EC.element_to_be_clickable((
        By.XPATH,
        "//button[contains(@class, 'lib-button') and contains(@class, 'green') and @type='submit']"
    ))
)
        logger.info("Кнопка «Авторизоваться» найдена")

        # 7. Проверка состояния кнопки ДО клика
        is_disabled = submit_button.get_attribute("disabled")
        logger.info(f"Кнопка заблокирована (disabled): {is_disabled}")

        if is_disabled:
            logger.error("Кнопка 'Авторизоваться' заблокирована. Пытаемся разблокировать через JS...")
            try:
                driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
                time.sleep(1)
                is_disabled_after = submit_button.get_attribute("disabled")
                logger.info(f"Состояние кнопки после разблокировки: disabled={is_disabled_after}")
            except Exception as e:
                logger.error(f"Не удалось разблокировать кнопку: {e}")
                return

        # 8. Клик по кнопке (с повторами)
        if click_with_retries(submit_button, driver):
            logger.info("Авторизация инициирована (клик).")
        else:
            # Если клики не сработали — пробуем Enter
            logger.warning("Клик не сработал. Пробуем отправить Enter на кнопку.")
            submit_button.send_keys(Keys.ENTER)
            logger.info("Отправлен Enter на кнопку «Авторизоваться».")

        # 9. Ждём полной загрузки страницы после авторизации
        logger.info("Ожидание загрузки страницы после авторизации...")
        wait_for_page_load(driver, timeout=30)

        # 10. Собираем JS‑ошибки после действия
        get_browser_logs(driver)

        # 11. Сохранение финальной страницы
        save_page_html(driver, 'main_company.html', 'work_parsed_pages')

        
        # 12. Комплексная проверка авторизации
        if check_authorization_status(driver):
            logger.info("✅ Авторизация успешна: все проверки пройдены")


        # 13. Пытаемся нажать по кнопке ПОКАЗАТЬ ЕЩЁ
        claims_row_info = scroll_and_click_show_more(driver) 
        
        # 14. Добавляем информацию в базу данных по каждой заявке
        for row_info in claims_row_info[1]:
            current_claim_info = dict()
            current_claim_info = parse_claim_from_html(row_info)
            current_claim_info.update(company_name=company_name)
            new_claim = await add_new_claim(claim_info=current_claim_info)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e=}")
    finally:
        scroll_and_click_header_then_logout(driver)
        if driver:
            driver.quit()
            logger.info("Драйвер закрыт")



def scroll_and_click_header_then_logout(driver, timeout=30):
    """
    1. Скроллит страницу наверх.
    2. Находит и нажимает на элемент header-login__link.
    3. Ищет во всплывающем контенте кнопку «Выйти» и нажимает её.

    Args:
        driver: экземпляр WebDriver
        timeout: время ожидания элементов в секундах

    Returns:
        bool: True, если все действия выполнены успешно, False — в случае ошибки
    """
    try:
        # 1. Гарантированный скролл наверх
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

        # 2. Поиск и клик по элементу header-login__link
        wait = WebDriverWait(driver, timeout)
        header_element = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[@class='header-login__link']"
            )
        ))

        if header_element.is_displayed() and header_element.is_enabled():
            try:
                header_element.click()
                print("✅ Элемент header-login__link успешно найден и нажата кнопка")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", header_element)
                print("✅ Элемент header-login__link нажата через JavaScript")
        else:
            print("❌ Элемент header-login__link найден, но не кликаем/не виден")
            return False

        # Небольшая пауза для появления всплывающего контента
        time.sleep(1)

        # 3. Поиск кнопки «Выйти» во всплывающем контенте
        logout_element = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//*[contains(text(), 'Выйти')]"
            )
        ))

        if logout_element.is_displayed() and logout_element.is_enabled():
            try:
                logout_element.click()
                print("✅ Кнопка «Выйти» успешно найдена и нажата")
                time.sleep(5)
                return True
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", logout_element)
                print("✅ Кнопка «Выйти» нажата через JavaScript")
                return True
        else:
            print("❌ Кнопка «Выйти» найдена, но не кликабельна/не видна")
            return False

    except TimeoutException as e:
        if "header-login__link" in str(e):
            print("❌ Элемент header-login__link не найден за отведённое время")
        elif "Выйти" in str(e):
            print("❌ Кнопка «Выйти» не найдена во всплывающем контенте за отведённое время")
        return False
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        return False





async def filled_base_of_all_companyes():
    login = ''
    password = ''
    company_name = ''

    for key, value in company_access.items():
        company_name = value[0]
        login = value[1]
        password = value[2]
        await filled_claims_to_base(login, password, company_name) 

    logger.info(f"Наполнение базы данных по всем компаниям успешно проведено")
    print(f"filled_base_of_all_companyes: Наполнение базы данных по всем компаниям успешно проведено")



def get_jsond_data_by_claim(company_name:str, claim_id:str | list) -> list:
    """Возвращает json данные по заявке"""
    login, password = [ (value[1], value[2]) for key, value in company_access.items() if value[0].lower() == company_name.lower()][0]

    logger.info(f"Приступили к поиску заявки с ID = {claim_id} для УК {company_name} с целью обновления её статуса")
    print(f"Приступили к поиску заявки с ID = {claim_id} для УК {company_name} с целью обновления её статуса")

    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 30)

        # 1. Загрузка страницы
        driver.get("https://eds.mosreg.ru/")
        logger.info(f"Страница загружена: {driver.current_url}")
        save_page_html(driver, 'login_page.html', 'work_parsed_pages')

        
        scroll_and_click_login_link(driver)
        
        # 2. Удаление оверлея
        remove_overlay(driver)

        # 3. Поиск контейнера формы
        logger.info("Ожидание видимости контейнера формы...")
        form_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.login-form'))
        )
        if form_container:
            logger.info("Контейнер формы найден - выделяем его...")
            driver.execute_script("arguments[0].style.border='3px solid red'", form_container)

        # 4. Поле email
        logger.info("Поиск поля email...")
        email_field = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'dd-lib-input[formcontrolname="login-form-email"] input'
            ))
        )
        if email_field:
            logger.info("Поле email найдено - выделяем его...")
            driver.execute_script("arguments[0].style.background='yellow'", email_field)
        email_field.clear()
        email_field.send_keys(login)
        print("Email введен")
        logger.info(f"Email введён: {email_field.get_attribute('value')}")

        # 5. Поле пароля
        password_field = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@placeholder='Пароль' and @type='password']"
            ))
        )
        logger.info("Поле пароля найдено")
        password_field.clear()
        
        password_field.send_keys(password)
        print("Пароль введен введен")
        logger.info(f"Пароль введён: {len(password_field.get_attribute('value'))} символов")

        # 6. Кнопка «Авторизоваться»
        submit_button = wait.until(
    EC.element_to_be_clickable((
        By.XPATH,
        "//button[contains(@class, 'lib-button') and contains(@class, 'green') and @type='submit']"
    ))
)
        logger.info("Кнопка «Авторизоваться» найдена")

        # 7. Проверка состояния кнопки ДО клика
        is_disabled = submit_button.get_attribute("disabled")
        logger.info(f"Кнопка заблокирована (disabled): {is_disabled}")

        if is_disabled:
            logger.error("Кнопка 'Авторизоваться' заблокирована. Пытаемся разблокировать через JS...")
            try:
                driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
                time.sleep(1)
                is_disabled_after = submit_button.get_attribute("disabled")
                logger.info(f"Состояние кнопки после разблокировки: disabled={is_disabled_after}")
            except Exception as e:
                logger.error(f"Не удалось разблокировать кнопку: {e}")
                return

        # 8. Клик по кнопке (с повторами)
        if click_with_retries(submit_button, driver):
            logger.info("Авторизация инициирована (клик).")
        else:
            # Если клики не сработали — пробуем Enter
            logger.warning("Клик не сработал. Пробуем отправить Enter на кнопку.")
            submit_button.send_keys(Keys.ENTER)
            logger.info("Отправлен Enter на кнопку «Авторизоваться».")

        # 9. Ждём полной загрузки страницы после авторизации
        logger.info("Ожидание загрузки страницы после авторизации...")
        wait_for_page_load(driver, timeout=30)

        # 10. Собираем JS‑ошибки после действия
        get_browser_logs(driver)

        # 11. Сохранение финальной страницы
        save_page_html(driver, 'main_company.html', 'work_parsed_pages')

        
        # 12. Комплексная проверка авторизации
        if check_authorization_status(driver):
            logger.info("✅ Авторизация успешна: все проверки пройдены")
        
        try:
            claims_actual_info = []
            if not isinstance(claim_id, list):
                        
                print(f"Пытаемся получить json данные по заявке c ID={claim_id}")

                try:
                    # Открываем страницу
                    driver.get(f"https://eds.mosreg.ru/api/claim/{claim_id}")

                    # Ждём появления элемента <pre> с JSON (максимум 10 секунд)
                    wait = WebDriverWait(driver, 10)
                    json_element = wait.until(
                        EC.presence_of_element_located((By.TAG_NAME, "pre"))
                    )
                    raw_json = json_element.text

                    if not raw_json.strip():
                        print(f"Получен пустой JSON для заявки {claim_id}")
                        
                    # Парсим JSON
                    data = json.loads(raw_json)
                    print(f"JSON успешно получен: {type(data)}")

                    # Отладочная печать структуры
                    print("Структура данных (первые уровни):")
                    #print(json.dumps({k: data[k] for k in list(data.keys())[:3]}, indent=2, ensure_ascii=False))


                    # Безопасное извлечение данных с учётом реальной структуры
                    value_data = data.get("value", {})
                    claim_data = value_data.get("claim", {})

                    claim_id_val = claim_data.get("id", None)
                    status_name = claim_data.get("statusName", None)
                    deadline = claim_data.get("deadline", None)
                    type_data = claim_data.get("type", {})
                    description = type_data.get("description", None) if type_data else None

                    claims_actual_info.append((claim_id_val, status_name, deadline, description))
                    #print(f"claims_actual_info={claims_actual_info}")
                    time.sleep(0.2)

                except NoSuchElementException:
                    print(f"Элемент <pre> не найден для заявки {claim_id}. Возможно, JSON не отображается или страница не загрузилась.")
                except TimeoutException:
                    print(f"Таймаут ожидания JSON для заявки {claim_id} (10 секунд).")
                except json.JSONDecodeError as e:
                    print(f"Ошибка парсинга JSON для заявки {claim_id}: {e}")
                    print(f"Текст ответа (первые 500 символов): {raw_json[:500] if 'raw_json' in locals() else 'Недоступен'}")
                except Exception as e:
                    print(f"Неожиданная ошибка для заявки {claim_id}: {e}")
            else:
                
                for item in claim_id:
                    print(f"Пытаемся получить json данные по заявке c ID={item}")

                    try:
                        # Открываем страницу
                        driver.get(f"https://eds.mosreg.ru/api/claim/{item}")

                        # Ждём появления элемента <pre> с JSON (максимум 10 секунд)
                        wait = WebDriverWait(driver, 10)
                        json_element = wait.until(
                            EC.presence_of_element_located((By.TAG_NAME, "pre"))
                        )
                        raw_json = json_element.text

                        if not raw_json.strip():
                            print(f"Получен пустой JSON для заявки {item}")
                            continue

                        # Парсим JSON
                        data = json.loads(raw_json)
                        print(f"JSON успешно получен: {type(data)}")

                        # Отладочная печать структуры
                        print("Структура данных (первые уровни):")
                        print(json.dumps({k: data[k] for k in list(data.keys())[:3]}, indent=2, ensure_ascii=False))


                        # Безопасное извлечение данных с учётом реальной структуры
                        value_data = data.get("value", {})
                        claim_data = value_data.get("claim", {})

                        claim_id_val = claim_data.get("id", None)
                        status_name = claim_data.get("statusName", None)
                        deadline = claim_data.get("deadline", None)
                        type_data = claim_data.get("type", {})
                        description = type_data.get("description", None) if type_data else None

                        claims_actual_info.append((claim_id_val, status_name, deadline, description))
                        #print(f"claims_actual_info={claims_actual_info}")

                    except NoSuchElementException:
                        print(f"Элемент <pre> не найден для заявки {item}. Возможно, JSON не отображается или страница не загрузилась.")
                    except TimeoutException:
                        print(f"Таймаут ожидания JSON для заявки {item} (10 секунд).")
                    except json.JSONDecodeError as e:
                        print(f"Ошибка парсинга JSON для заявки {item}: {e}")
                        print(f"Текст ответа (первые 500 символов): {raw_json[:500] if 'raw_json' in locals() else 'Недоступен'}")
                    except Exception as e:
                        print(f"Неожиданная ошибка для заявки {item}: {e}")

                
                print("Обработка завершена. Итоговый список: (временно закоментирован)")
                #print(claims_actual_info)
                return claims_actual_info
            

        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса: {e}")
        except json.JSONDecodeError as e:
            print(f"Ответ не является валидным JSON: {e}")
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
    finally:
        if driver:
            driver.get("https://eds.mosreg.ru/")
            time.sleep(3)
            scroll_and_click_header_then_logout(driver)
            driver.quit()
            logger.info("Драйвер закрыт")
    






def search_and_extract_data(company_name:str, search_text="6213774", timeout=10):
    """
    Выполняет поиск по странице: вводит текст в поле, нажимает кнопку поиска, извлекает данные.

    Args:
        driver: экземпляр WebDriver
        search_text: строка для ввода в поле поиска
        timeout: время ожидания элементов в секундах

    Returns:
        tuple: (введённый_текст, статус_заявки, срок_выполнения) или (введённый_текст, None, None) при ошибке
    """
    # ищем пароль и логин управляющей компании, для которой ищем заявку
    
    login, password = [ (value[1], value[2]) for key, value in company_access.items() if value[0].lower() == company_name.lower()][0]

    logger.info(f"Приступили к поиску заявки с ID = {search_text} для УК {company_name} с целью обновления её статуса")
    print(f"Приступили к поиску заявки с ID = {search_text} для УК {company_name} с целью обновления её статуса")

    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 30)

        # 1. Загрузка страницы
        driver.get("https://eds.mosreg.ru/")
        logger.info(f"Страница загружена: {driver.current_url}")
        save_page_html(driver, 'login_page.html', 'work_parsed_pages')

        
        scroll_and_click_login_link(driver)
        
        # 2. Удаление оверлея
        remove_overlay(driver)

        # 3. Поиск контейнера формы
        logger.info("Ожидание видимости контейнера формы...")
        form_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.login-form'))
        )
        if form_container:
            logger.info("Контейнер формы найден - выделяем его...")
            driver.execute_script("arguments[0].style.border='3px solid red'", form_container)

        # 4. Поле email
        logger.info("Поиск поля email...")
        email_field = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'dd-lib-input[formcontrolname="login-form-email"] input'
            ))
        )
        if email_field:
            logger.info("Поле email найдено - выделяем его...")
            driver.execute_script("arguments[0].style.background='yellow'", email_field)
        email_field.clear()
        email_field.send_keys(login)
        print("Email введен")
        logger.info(f"Email введён: {email_field.get_attribute('value')}")

        # 5. Поле пароля
        password_field = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@placeholder='Пароль' and @type='password']"
            ))
        )
        logger.info("Поле пароля найдено")
        password_field.clear()
        
        password_field.send_keys(password)
        print("Пароль введен введен")
        logger.info(f"Пароль введён: {len(password_field.get_attribute('value'))} символов")

        # 6. Кнопка «Авторизоваться»
        submit_button = wait.until(
    EC.element_to_be_clickable((
        By.XPATH,
        "//button[contains(@class, 'lib-button') and contains(@class, 'green') and @type='submit']"
    ))
)
        logger.info("Кнопка «Авторизоваться» найдена")

        # 7. Проверка состояния кнопки ДО клика
        is_disabled = submit_button.get_attribute("disabled")
        logger.info(f"Кнопка заблокирована (disabled): {is_disabled}")

        if is_disabled:
            logger.error("Кнопка 'Авторизоваться' заблокирована. Пытаемся разблокировать через JS...")
            try:
                driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
                time.sleep(1)
                is_disabled_after = submit_button.get_attribute("disabled")
                logger.info(f"Состояние кнопки после разблокировки: disabled={is_disabled_after}")
            except Exception as e:
                logger.error(f"Не удалось разблокировать кнопку: {e}")
                return

        # 8. Клик по кнопке (с повторами)
        if click_with_retries(submit_button, driver):
            logger.info("Авторизация инициирована (клик).")
        else:
            # Если клики не сработали — пробуем Enter
            logger.warning("Клик не сработал. Пробуем отправить Enter на кнопку.")
            submit_button.send_keys(Keys.ENTER)
            logger.info("Отправлен Enter на кнопку «Авторизоваться».")

        # 9. Ждём полной загрузки страницы после авторизации
        logger.info("Ожидание загрузки страницы после авторизации...")
        wait_for_page_load(driver, timeout=30)

        # 10. Собираем JS‑ошибки после действия
        get_browser_logs(driver)

        # 11. Сохранение финальной страницы
        save_page_html(driver, 'main_company.html', 'work_parsed_pages')

        
        # 12. Комплексная проверка авторизации
        if check_authorization_status(driver):
            logger.info("✅ Авторизация успешна: все проверки пройдены")
        
        try:
                
            wait = WebDriverWait(driver, timeout)

            actual_status_info = None

            if not isinstance(search_text, list):
                # Обработка одиночной заявки
                print(f"🔎 Обработка одиночной заявки: {search_text}")

                try:
                    # 1. Поиск и ввод в поле поиска
                    print("🔎 Ищем поле ввода...")
                    input_field = wait.until(
                        EC.presence_of_element_located((
                            By.XPATH,
                    "//input[contains(@class, 'search-input') and @type='text']"
                ))
                    )
                    print("✅ Поле ввода найдено")

                    input_field.clear()
                    input_field.send_keys(search_text)
                    print(f"📝 Текст '{search_text}' введён в поле поиска")

                    # 2. Поиск и клик по кнопке поиска
                    print("🔎 Ищем кнопку поиска...")
                    search_button = wait.until(
                        EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[contains(@class, 'head-filter__search_event') and contains(text(), 'Искать по всем заявкам')]"
                ))
                    )
                    search_button.click()
                    print("✅ Кнопка «Искать по всем заявкам» нажата")

                    # Ожидание стабилизации DOM
                    time.sleep(2)
                    wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

                    # Ждём исчезновения спиннера загрузки (если есть)
                    try:
                        wait.until(EC.invisibility_of_element_located((By.ID, "loading-spinner")))
                    except:
                        pass

                    # 3. Поиск статуса заявки с обработкой Stale Element
                    print("🔎 Ищем статус заявки...")
                    status_element = _find_element_with_retry(
                        wait,
                        By.XPATH,
                        "//span[contains(@class, 'claim-status-name')]",
                        max_attempts=3
                    )
                    claim_status = status_element.text.strip() if status_element else None
                    print(f"✅ Найден статус заявки: '{claim_status}'")

                    # 4. Поиск срока выполнения с обработкой Stale Element
                    print("🔎 Ищем срок выполнения...")
                    deadline_element = _find_element_with_retry(
                        wait,
                        By.XPATH,
                        "//td[contains(@class, 'cdk-column-deadline')]//span",
                        max_attempts=3
                    )
                    deadline = deadline_element.text.strip() if deadline_element else None
                    print(f"✅ Найден срок выполнения: '{deadline}'")

                    return (search_text, claim_status, deadline)

                except Exception as e:
                    print(f"❌ Ошибка при обработке заявки {search_text}: {e}")
                    return (search_text, None, None)

            else:
                # Обработка нескольких заявок
                print("Планируем актуализировать информацию по нескольким заявкам")
                actual_status_info = list()

                for claim_id in search_text:
                    print(f"\n🔎 Обработка заявки: {claim_id}")

                    try:
                        # 1. Поиск и ввод в поле поиска
                        print("🔎 Ищем поле ввода...")
                        input_field = wait.until(
                            EC.presence_of_element_located((
                        By.XPATH,
                        "//input[contains(@class, 'search-input') and @type='text']"
                    ))
                        )
                        print("✅ Поле ввода найдено")

                        input_field.clear()
                        input_field.send_keys(claim_id)
                        print(f"📝 Текст '{claim_id}' введён в поле поиска")

                        # 2. Поиск и клик по кнопке поиска
                        print("🔎 Ищем кнопку поиска...")
                        search_button = wait.until(
                            EC.element_to_be_clickable((
                        By.XPATH,
                        "//div[contains(@class, 'head-filter__search_event') and contains(text(), 'Искать по всем заявкам')]"
                    ))
                        )
                        search_button.click()
                        print("✅ Кнопка «Искать по всем заявкам» нажата")

                        # Ожидание стабилизации DOM
                        time.sleep(2)
                        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

                        # Ждём исчезновения спиннера загрузки
                        try:
                            wait.until(EC.invisibility_of_element_located((By.ID, "loading-spinner")))
                        except:
                            pass

                        # 3. Поиск статуса заявки с повторными попытками
                        print("🔎 Ищем статус заявки...")
                        status_element = _find_element_with_retry(wait, By.XPATH, "//span[contains(@class, 'claim-status-name')]", max_attempts=3)
                        claim_status = status_element.text.strip() if status_element else None
                        print(f"✅ Найден статус заявки: '{claim_status}'")

                        # 4. Поиск срока выполнения с повторными попытками
                        print("🔎 Ищем срок выполнения...")
                        deadline_element = _find_element_with_retry(wait, By.XPATH, "//td[contains(@class, 'cdk-column-deadline')]//span", max_attempts=3)
                        deadline = deadline_element.text.strip() if deadline_element else None
                        print(f"✅ Найден срок выполнения: '{deadline}'")

                        actual_status_info.append((claim_id, claim_status, deadline))


                    except Exception as e:
                        print(f"❌ Ошибка при обработке заявки {claim_id}: {e}")
                        actual_status_info.append((claim_id, None, None))

                print(f"Актуальная информация по всем заявкам:\n{actual_status_info}")
                return actual_status_info

        except Exception as e:
            print(f"❌ search_and_extract_data: Произошла ошибка: {e}")
        finally:
            if driver:
                driver.quit()
                print("search_and_extract_data: Драйвер закрыт")
    
    except Exception as e:
        print(f"search_and_extract_data: Произошла ошибка: {e}")
        return None
        

def _find_element_with_retry(wait, by, locator, max_attempts=3):
    """Вспомогательная функция для поиска элемента с повторными попытками при StaleElement"""
    for attempt in range(max_attempts):
        try:
            element = wait.until(EC.presence_of_element_located((by, locator)))
            return element
        except StaleElementReferenceException:
            if attempt == max_attempts - 1:
                raise
            print(f"⚠️ Попытка {attempt + 1}: элемент устарел, повторяем поиск...")
            time.sleep(1)
    return None


async def find_info_of_new_claims():
    """Собирает информацию о новых заявках по всем управляющим
    компаниям и принимает их В РАБОТУ"""
    
    new_claims_by_company = dict()

    for value in list(company_access.values()):
        print(f"Получаем информацию по новым заявкам для управляющей компании {value[0]}")
        current_new_claims = find_info_of_new_claims_by_company(value[0])
        await add_new_claims(current_new_claims)
        
        new_claims_by_company.update({f"{value[0]}" : current_new_claims})
    
    print(f'find_info_of_new_claims: {new_claims_by_company=}')
    logger.info(f"{new_claims_by_company=}")
    return new_claims_by_company
        



def find_info_of_new_claims_by_company(company_name:str):
    
    login, password = [ (value[1], value[2]) for key, value in company_access.items() if value[0].lower() == company_name.lower()][0]
    
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 30)

        # 1. Загрузка страницы
        driver.get("https://eds.mosreg.ru/")
        logger.info(f"Страница загружена: {driver.current_url}")
        save_page_html(driver, 'login_page.html', 'work_parsed_pages')

        
        scroll_and_click_login_link(driver)
        # 2. Удаление оверлея
        remove_overlay(driver)

        # 3. Поиск контейнера формы
        logger.info("Ожидание видимости контейнера формы...")
        form_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.login-form'))
        )
        if form_container:
            logger.info("Контейнер формы найден - выделяем его...")
            driver.execute_script("arguments[0].style.border='3px solid red'", form_container)

        # 4. Поле email
        logger.info("Поиск поля email...")
        email_field = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'dd-lib-input[formcontrolname="login-form-email"] input'
            ))
        )
        if email_field:
            logger.info("Поле email найдено - выделяем его...")
            driver.execute_script("arguments[0].style.background='yellow'", email_field)
        email_field.clear()
        email_field.send_keys(login)
        logger.info(f"Email введён: {email_field.get_attribute('value')}")

        # 5. Поле пароля
        password_field = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@placeholder='Пароль' and @type='password']"
            ))
        )
        logger.info("Поле пароля найдено")
        password_field.clear()
        
        password_field.send_keys(password)
        logger.info(f"Пароль введён: {len(password_field.get_attribute('value'))} символов")

        # 6. Кнопка «Авторизоваться»
        submit_button = wait.until(
    EC.element_to_be_clickable((
        By.XPATH,
        "//button[contains(@class, 'lib-button') and contains(@class, 'green') and @type='submit']"
    ))
)
        logger.info("Кнопка «Авторизоваться» найдена")

        # 7. Проверка состояния кнопки ДО клика
        is_disabled = submit_button.get_attribute("disabled")
        logger.info(f"Кнопка заблокирована (disabled): {is_disabled}")

        if is_disabled:
            logger.error("Кнопка 'Авторизоваться' заблокирована. Пытаемся разблокировать через JS...")
            try:
                driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
                time.sleep(1)
                is_disabled_after = submit_button.get_attribute("disabled")
                logger.info(f"Состояние кнопки после разблокировки: disabled={is_disabled_after}")
            except Exception as e:
                logger.error(f"Не удалось разблокировать кнопку: {e}")
                return

        # 8. Клик по кнопке (с повторами)
        if click_with_retries(submit_button, driver):
            logger.info("Авторизация инициирована (клик).")
        else:
            # Если клики не сработали — пробуем Enter
            logger.warning("Клик не сработал. Пробуем отправить Enter на кнопку.")
            submit_button.send_keys(Keys.ENTER)
            logger.info("Отправлен Enter на кнопку «Авторизоваться».")

        # 9. Ждём полной загрузки страницы после авторизации
        logger.info("Ожидание загрузки страницы после авторизации...")
        wait_for_page_load(driver, timeout=30)

        # 10. Собираем JS‑ошибки после действия
        get_browser_logs(driver)

        # 11. Сохранение финальной страницы
        save_page_html(driver, 'main_company.html', 'work_parsed_pages')

        # 12. Комплексная проверка авторизации
        if check_authorization_status(driver):
            logger.info("✅ Авторизация успешна: все проверки пройдены")
            
            
            # 13. Попытка взаимодействия с элементом «НОВЫЕ»
            try:
                # Пытаемся кликнуть по элементу «НОВЫЕ»
                if click_new_claims_by_icon(driver, wait):
                # Если клик удался, ждём загрузки и сохраняем страницу
                    wait_for_page_load(driver, timeout=15)
                    save_page_html(driver, 'new_claims.html', 'work_parsed_pages')
                    logger.info("Страница с новыми заявками успешно сохранена")
                else:
                    logger.error("Не удалось перейти к новым заявкам")

            except TimeoutException:
                logger.warning("Элемент «НОВЫЕ» не найден или не кликаем в отведённое время")
            except Exception as e:
                logger.error(f"Ошибка при работе с элементом «НОВЫЕ»: {e}")
            
            # 14.Собираем информацию по новым заявкам в виде словаря
            try:
                new_claims_data = collect_new_claims_data(driver)
                print(f"Information of new claims: {new_claims_data=}")
                logger.info(f"Information of new claims: {new_claims_data=}")
            except Exception as e:
                logger.error(f"Произошла ошибка при получении информации по новым заявкам в виде словаря {e=}")
                
            # 15. Получаем детальную информацию о всех новых заявках
            try:
                all_claim_info = click_all_claim_details_and_save(driver)
                if all_claim_info:
                    print("Информация о всех новых заявках:", all_claim_info)
                    logger.info(f"Информация о всех новых заявках: {all_claim_info=}")
                    return new_claims_data
                else:
                    print("Не удалось получить информацию о заявках")
                    logger.warning("Не удалось получить информацию о новых заявках. Возможно их нет")
            except Exception as e:
                    logger.error(f"При получении подробной информации о новых заявках произошла ошибка: {e=}")
        else:
            logger.error("❌ Авторизация не прошла — не удалось подтвердить статус авторизации")

            # Дополнительная диагностика
            try:
                # Ищем сообщения об ошибках
                error_selectors = [
                    ".error-message",
            ".alert-danger",
            ".text-danger",
            "[role='alert']",
            ".notification.error"
        ]
                for selector in error_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        error_text = element.text.strip()
                        if error_text:
                            logger.error(f"На странице обнаружено сообщение об ошибке: {error_text}")
                            break
                    except:
                        continue

                # Проверяем CAPTCHA
                try:
                    captcha_element = driver.find_element(
                                (By.XPATH, "//*[contains(text(), 'CAPTCHA') or contains(@id, 'captcha') or contains(@class, 'captcha')]")
                                   )
                    if captcha_element.is_displayed():
                        logger.error("На странице обнаружена CAPTCHA — требуется ручное подтверждение.")
                except:
                    pass  # CAPTCHA не найдена или не видна

                current_url = driver.current_url
                page_title = driver.title
                logger.info(f"Текущий URL: {current_url}")
                logger.info(f"Заголовок страницы: {page_title}")

            except TimeoutException as e:
                logger.error(f"Таймаут ожидания элемента: {e}")
        if driver:
            save_page_html(driver, 'timeout_page.html', 'work_parsed_pages')
            driver.save_screenshot('timeout_screenshot.png')
    except WebDriverException as e:
        logger.error(f"Ошибка WebDriver: {e}")
        if driver:
            save_page_html(driver, 'webdriver_error_page.html', 'work_parsed_pages')
            driver.save_screenshot('webdriver_error_screenshot.png')
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {type(e).__name__}: {e}")
        if driver:
            save_page_html(driver, 'unexpected_error_page.html', 'work_parsed_pages')
            driver.save_screenshot('unexpected_error_screenshot.png')
    finally:
        if driver:
            #logger.info("Браузер остаётся открытым. Нажмите Enter в консоли для закрытия...")
            #input("Чтобы остановить скрипт, нажмите Enter")  # Ожидание ввода от пользователя
            scroll_and_click_header_then_logout(driver)
            driver.quit()
            logger.info("Драйвер закрыт")



if __name__ == "__main__":
    import asyncio

    #asyncio.run(filled_base_of_all_companyes())
    #search_and_extract_data("Радуга", "6185598")
    #search_and_extract_data("Радуга", ["6185598", "6184252", "6180019"])
    #asyncio.run(find_info_of_new_claims())
    #get_jsond_data_by_claim("Радуга", "6185598")
    get_jsond_data_by_claim("Радуга", ["6185598", "6184252", "6180019"])

    
    
    
