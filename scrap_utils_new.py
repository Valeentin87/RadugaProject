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
