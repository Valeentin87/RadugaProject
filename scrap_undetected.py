import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, ElementClickInterceptedException
from selenium.webdriver.common.keys import Keys
import logging
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

def create_driver():
    options = uc.ChromeOptions()
    
    # Обязательные флаги для headless на сервере
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    
    # Имитация пользователя
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
    options.add_argument("--accept-language=ru-RU,ru;q=0.9")
    
    # Подавление логов
    options.add_argument('--log-level=3')
    options.add_argument('--silent')
    
    driver = uc.Chrome(
        options=options,
        headless=True,
        version_main=144,
        enable_cdp_events=True
    )
    return driver

def save_login_page(driver):
    try:
        with open('login_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info("HTML страницы входа сохранён: login_page.html")
    except Exception as e:
        logger.error(f"Ошибка при сохранении login_page.html: {e}")

def save_final_page(driver):
    try:
        with open('final_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info("HTML финальной страницы сохранён: final_page.html")
    except Exception as e:
        logger.error(f"Ошибка при сохранении final_page.html: {e}")

def get_visible_button(driver, css_selector):
    """Возвращает первую видимую и активную кнопку по селектору"""
    buttons = driver.find_elements(By.CSS_SELECTOR, css_selector)
    for btn in buttons:
        try:
            if btn.is_displayed() and btn.is_enabled():
                return btn
        except:
            continue
    return None

def safe_click_button(driver, css_selector, max_retries=3):
    """Надёжно кликает по кнопке, переискивая её перед каждой попыткой"""
    for attempt in range(max_retries):
        try:
            button = get_visible_button(driver, css_selector)
            if not button:
                logger.warning(f"Попытка {attempt + 1}: кнопка не найдена/неактивна")
                time.sleep(2)
                continue

            button.click()
            logger.info(f"Клик успешен (попытка {attempt + 1})")
            return True
        except ElementClickInterceptedException as e:
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}. Ждём 3 сек.")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при клике (попытка {attempt + 1}): {e}")
            time.sleep(2)
    return False

def check_and_remove_overlays(driver):
    """Проверяет и удаляет возможные оверлеи"""
    overlays = [
        "div.cdk-overlay-container",
        "div.modal-backdrop",
        "div.overlay",
        ".popup-overlay"
    ]
    for selector in overlays:
        try:
            overlay = driver.find_element(By.CSS_SELECTOR, selector)
            if overlay.is_displayed():
                driver.execute_script("arguments[0].remove();", overlay)
                logger.info(f"Оверлей удалён: {selector}")
        except:
            continue

def safe_fill_field(driver, locator, value, field_name):
    """Надёжно заполняет поле с проверкой результата"""
    try:
        element = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(locator))
        element.clear()
        element.send_keys(value)

        # Проверяем, что значение установилось
        actual_value = element.get_attribute("value")
        if actual_value != value:
            logger.warning(f"{field_name}: ожидалось '{value}', получено '{actual_value}'. Пробуем через JS.")
            driver.execute_script(f"arguments[0].value = '{value}';", element)
            actual_value = element.get_attribute("value")

        logger.info(f"{field_name} введён: {actual_value}")
        return element
    except Exception as e:
        logger.error(f"Ошибка при заполнении {field_name}: {e}")
        return None

def get_browser_logs(driver):
    """Собирает логи браузера (JS‑ошибки)"""
    try:
        logs = driver.get_log("browser")
        for log in logs:
            if log["level"] == "SEVERE":
                logger.error(f"JS‑ошибка: {log['message']}")
    except:
        logger.warning("Не удалось получить логи браузера.")

def main():
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 15)

        driver.get("https://eds.mosreg.ru/#login")
        logger.info(f"Страница загружена: {driver.current_url}")

        save_login_page(driver)
        check_and_remove_overlays(driver)  # Удаляем оверлеи до поиска элементов

        # 1. Поиск контейнера формы
        form_container = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.login-form')))
        logger.info("Контейнер формы найден")

        # 2. Поле email
        email_field = safe_fill_field(
            driver,
            (By.CSS_SELECTOR, 'dd-lib-input[formcontrolname="login-form-email"] input'),
            "5003108379",
            "Email"
        )
        if not email_field:
            raise Exception("Не удалось заполнить поле email")

        # 3. Поле пароля
        password_field = safe_fill_field(
            driver,
            (By.XPATH, "//input[@placeholder='Пароль' and @type='password']"),
            "pVK8Wtx7",
            "Пароль"
        )
        if not password_field:
            raise Exception("Не удалось заполнить поле пароля")

        # 4. Поиск видимой и активной кнопки «Авторизоваться»
        submit_button = get_visible_button(driver, "button.lib-button.green")
        if not submit_button:
            logger.error("Не найдено видимой активной кнопки 'Авторизоваться'")
            return

        logger.info("Кнопка «Авторизоваться» найдена и готова к клику")

        # 5. Проверка состояния кнопки (disabled)
        is_disabled = submit_button.get_attribute("disabled")
        logger.info(f"Кнопка заблокирована (disabled): {is_disabled}")

        if is_disabled:
            logger.error("Кнопка 'Авторизоваться' заблокирована. Пытаемся разблокировать через JS...")
            try:
                driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
                time.sleep(0.5)
                is_disabled_after = submit_button.get_attribute("disabled")
                logger.info(f"Состояние кнопки после разблокировки: disabled={is_disabled_after}")
                
                if is_disabled_after:
                    logger.critical("Не удалось разблокировать кнопку. Авторизация невозможна.")
                    return
            except Exception as e:
                logger.error(f"Ошибка при разблокировке кнопки: {e}")
                return

        # 6. Дополнительная проверка: валидность ввода
        email_value = email_field.get_attribute("value")
        password_value = password_field.get_attribute("value")
        if not email_value or not password_value:
            logger.error("Одно из полей осталось пустым после заполнения!")
            return

        logger.info("Поля заполнены корректно. Готов к отправке формы.")

        # 7. Попытка клика по кнопке
        logger.info("Пытаемся кликнуть по кнопке 'Авторизоваться'...")
        if safe_click_button(driver, "button.lib-button.green"):
            logger.info("Авторизация инициирована (клик).")
        else:
            # Если клики не сработали — пробуем отправить Enter
            logger.warning("Клик не сработал. Пробуем отправить Enter на кнопку.")
            try:
                submit_button.send_keys(Keys.ENTER)
                logger.info("Отправлен Enter на кнопку «Авторизоваться».")
            except Exception as e:
                logger.error(f"Не удалось отправить Enter: {e}")

        # 8. Ожидание результата авторизации
        time.sleep(15)  # Время ожидания ответа сервера
        get_browser_logs(driver)

        # 9. Сохранение финальной страницы
        save_final_page(driver)

        # 10. Проверка результата
        current_url = driver.current_url
        page_title = driver.title
        logger.info(f"Текущий URL: {current_url}")
        logger.info(f"Заголовок страницы: {page_title}")

        if current_url != "https://eds.mosreg.ru/#login":
            logger.info("✅ Авторизация успешна: URL изменился.")
        else:
            logger.error("❌ Авторизация не прошла — URL не изменился.")

            # Дополнительная диагностика ошибок
            try:
                error_selectors = [
                    ".error-message", ".alert-danger", ".text-danger",
                    "[role='alert']", ".notification.error", "//*[contains(@class, 'error')]"
                ]
                for selector in error_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            text = el.text.strip()
                            if text:
                                logger.error(f"Сообщение об ошибке на странице: {text}")
                                break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Не удалось проверить сообщения об ошибках: {e}")

            # Проверка CAPTCHA
            try:
                captcha_text = driver.find_element(By.XPATH, "//*[contains(text(), 'CAPTCHA') or contains(text(), 'капча')]")
                if captcha_text.is_displayed():
                    logger.error("⚠️ На странице обнаружена CAPTCHA — требуется ручное подтверждение.")
            except:
                pass

        # 11. Финальная проверка состояния кнопки
        try:
            submit_button_final = get_visible_button(driver, "button.lib-button.green")
            if submit_button_final:
                final_disabled = submit_button_final.get_attribute("disabled")
                logger.info(f"Финальное состояние кнопки: disabled={final_disabled}")
            else:
                logger.warning("Финальная кнопка не найдена в DOM.")
        except Exception as e:
            logger.warning(f"Не удалось проверить финальное состояние кнопки: {e}")

    except TimeoutException as e:
        logger.error(f"Таймаут ожидания элемента: {e}")
        if driver:
            with open('timeout_page.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            driver.save_screenshot('timeout_screenshot.png')
    except WebDriverException as e:
        logger.error(f"Ошибка WebDriver: {e}")
        if driver:
            with open('webdriver_error_page.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            driver.save_screenshot('webdriver_error_screenshot.png')
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {type(e).__name__}: {e}")
        if driver:
            with open('unexpected_error_page.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            driver.save_screenshot('unexpected_error_screenshot.png')
    finally:
        if driver:
            driver.quit()
            logger.info("Драйвер закрыт")

if __name__ == "__main__":
    main()
