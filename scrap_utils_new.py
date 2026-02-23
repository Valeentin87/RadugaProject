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
import logging
import os
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('scrap_util.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
            "Дата обращения": date_text,
            "Категория": category_text,
            "Адрес": address_text,
            "Срочность": urgency_text,
            "Срок": deadline_text
        }

    return claims_data

# Пример использования:
# driver = webdriver.Chrome(options=create_chrome_options())
# driver.get("ваш_url")
# data = collect_new_claims_data(driver)
# print(data)




def wait_for_page_load(driver, timeout=30):
    """Ждёт полной загрузки страницы"""
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )
    time.sleep(1)  # Небольшая пауза для стабилизации

# ------- логика поиска кликабельных элементов для нажатия на НОВАЯ ЗАЯВКА и получения более подробной информации по ней с целью последующего принятия в работу -------

def click_first_claim_details_and_save(driver, wait_timeout=10):
    """
    Ищет элементы с классом 'claim-status', находит кликабельный элемент рядом с ним,
    кликает на первый найденный и сохраняет информацию о странице.


    Args:
        driver: экземпляр WebDriver
        wait_timeout: время ожидания элементов в секундах (по умолчанию 10 с)

    Returns:
        dict: информация о первой заявке или None при ошибке
    """
    wait = WebDriverWait(driver, wait_timeout)

    try:
        # Ждём появления элементов с классом claim-status
        status_elements = wait.until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "claim-status"))
        )

        if not status_elements:
            print("Не найдено элементов с классом 'claim-status'")
            return None

        print(f"Найдено элементов с классом 'claim-status': {len(status_elements)}")

        # Стратегии поиска кликабельного элемента — в порядке приоритета
        strategies = [
            # 1. Первая строка таблицы (наиболее вероятный кандидат)
            {
                'locator': "//tbody[@role='rowgroup']//tr[@role='row'][1]",
                'type': By.XPATH,
                'desc': 'Первая строка таблицы (tr[role="row"])'
            },
            # 2. Номер заявки в первой строке
            {
                'locator': "//tr[@role='row'][1]//td[contains(@class, 'cdk-column-id')]//span",
                'type': By.XPATH,
                'desc': 'Номер заявки в первой строке'
            },
            # 3. Статус в первой строке
            {
                'locator': "//tr[@role='row'][1]//span[@class='claim-status-name']",
                'type': By.XPATH,
                'desc': 'Статус заявки в первой строке'
            },
            # 4. Любая кликабельная ячейка в первой строке
            {
                'locator': "//tr[@role='row'][1]//*[@onclick or @href or contains(@class, 'click') or contains(@class, 'btn')]",
                'type': By.XPATH,
                'desc': 'Кликабельная ячейка в первой строке'
            }
        ]

        # Перебираем стратегии поиска
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
                    # Если обычный клик не сработал, пробуем через JavaScript
                    driver.execute_script("arguments[0].click();", clickable_element)

                # Ждём загрузки деталей заявки
                time.sleep(2)

                # Сохраняем информацию о текущей странице
                claim_info = save_claim_details(driver)
                if claim_info:
                    print("Информация о заявке успешно сохранена")
                    return claim_info
                else:
                    print("Не удалось сохранить информацию о заявке")

            except TimeoutException:
                print(f"Элемент не найден/не кликабелен: {strategy['desc']}")
                continue
            except Exception as e:
                print(f"Ошибка при клике по {strategy['desc']}: {e}")
                continue

        print("Не удалось найти кликабельный элемент ни для одного из claim-status")
        return None

    except Exception as e:
        print(f"Ошибка при поиске элементов claim-status: {e}")
        return None

def save_claim_details(driver):
    """
    Сохраняет информацию о детализированной странице заявки.

    Returns:
        dict с информацией о заявке или None
    """
    try:
        page_url = driver.current_url
        save_page_html(driver, 'first_new_claim_detail.html', 'work_parsed_pages')

        # Ищем заголовок или ключевые данные на странице деталей
        try:
            title_element = driver.find_element(
                By.XPATH,
                "//h1 | //h2 | //*[contains(@class, 'title') | contains(@class, 'header')]"
            )
            title = title_element.text.strip()
        except Exception:
            title = "Заголовок не найден"

        # Сохраняем скриншот для визуальной верификации
        timestamp = int(time.time())
        screenshot_path = f"claim_details_{timestamp}.png"
        driver.save_screenshot(screenshot_path)

        claim_info = {
            "url": page_url,
            "title": title,
            "screenshot": screenshot_path,
            "timestamp": timestamp
        }
        return claim_info
    except Exception as e:
        print(f"Ошибка при сохранении деталей заявки: {e}")
        return None


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



def main():
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 60)

        # 1. Загрузка страницы
        driver.get("https://eds.mosreg.ru/#login")
        logger.info(f"Страница загружена: {driver.current_url}")
        save_page_html(driver, 'login_page.html', 'work_parsed_pages')

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
        email_field.send_keys("5003108379")
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
        
        password_field.send_keys("pVK8Wtx7")
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

            # 15. Получаем детальную информацию о первой новой заявке
            try:
                first_claim_info = click_first_claim_details_and_save(driver)
                if first_claim_info:
                    print("Информация о первой заявке:", first_claim_info)
                    logger.info(f"Информация о первой заявке: {first_claim_info=}")
                else:
                    print("Не удалось получить информацию о заявке")
                    logger.warning("Не удалось получить иныормацию о первой заявке. ВОзможно их нет")
            except Exception as e:
                    logger.error(f"При получении подробной информации о первой новой заявке произошла ошибка: {e=}")
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
            logger.info("Браузер остаётся открытым. Нажмите Enter в консоли для закрытия...")
            input("Чтобы остановить скрипт, нажмите Enter")  # Ожидание ввода от пользователя
            driver.quit()
            logger.info("Драйвер закрыт")

if __name__ == "__main__":
    main()
