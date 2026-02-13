from selenium import webdriver
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
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--single-process')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    options.add_argument("--accept-language=ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7")
    return options

def save_login_page(driver):
    """Сохраняет HTML страницы входа"""
    try:
        with open('login_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info("HTML страницы входа сохранён: login_page.html")
    except Exception as e:
        logger.error(f"Ошибка при сохранении login_page.html: {e}")

def save_final_page(driver):
    """Сохраняет HTML финальной страницы (после попытки авторизации)"""
    try:
        with open('final_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.info("HTML финальной страницы сохранён: final_page.html")
    except Exception as e:
        logger.error(f"Ошибка при сохранении final_page.html: {e}")

def click_with_retries(element, driver, max_retries=3):
    """Кликает по элементу с повторными попытками"""
    for attempt in range(max_retries):
        try:
            time.sleep(2)
            element.click()
            logger.info(f"Клик успешен (попытка {attempt + 1})")
            return True
        except ElementClickInterceptedException as e:
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}. Ждём 5 сек и пробуем снова.")
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

def main():
    driver = None
    try:
        options = create_chrome_options()
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 60)

        # 1. Загрузка страницы
        driver.get("https://eds.mosreg.ru/#login")
        logger.info(f"Страница загружена: {driver.current_url}")

        # 2. Сохранение HTML страницы входа
        save_login_page(driver)

        # 3. Удаление оверлея (приоритет!)
        remove_overlay(driver)

        # 4. Поиск контейнера формы
        form_container = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.login-form'))
        )
        logger.info("Контейнер формы найден")

        # 5. Поле email
        email_field = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'dd-lib-input[formcontrolname="login-form-email"] input'
            ))
        )
        logger.info("Поле email найдено")
        email_field.send_keys("5003108379")  # ВАШ ЛОГИН
        time.sleep(1.5)
        logger.info(f"Email введён: {email_field.get_attribute('value')}")

        # 6. Поле пароля
        password_field = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//input[@placeholder='Пароль' and @type='password']"
            ))
        )
        logger.info("Поле пароля найдено")
        password_field.send_keys("pVK8Wtx7")  # ВАШ ПАРОЛЬ
        time.sleep(2)
        logger.info(f"Пароль введён: {len(password_field.get_attribute('value'))} символов")

        # 7. Кнопка «Авторизоваться»
        submit_button = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(@class,'lib-button') and contains(@class,'green') and @type='submit' and .//span[contains(normalize-space(),'Авторизоваться')] ]"
            ))
        )
        logger.info("Кнопка «Авторизоваться» найдена")

        # 8. Проверка состояния кнопки ДО клика
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

        # 9. Клик по кнопке (с повторами)
        if click_with_retries(submit_button, driver):
            logger.info("Авторизация инициирована (клик).")
        else:
            # Если клики не сработали — пробуем Enter
            logger.warning("Клик не сработал. Пробуем отправить Enter на кнопку.")
            submit_button.send_keys(Keys.ENTER)
            logger.info("Отправлен Enter на кнопку «Авторизоваться».")

        # 10. Ждём редиректа и проверяем результат
        time.sleep(20)  # Увеличенное ожидание
        get_browser_logs(driver)
                # 10. Ждём редиректа и проверяем результат
        time.sleep(20)  # Увеличенное ожидание ответа сервера
        get_browser_logs(driver)  # Собираем JS‑ошибки после действия

        # 11. Сохранение финальной страницы (всегда!)
        save_final_page(driver)

        # 12. Проверка результата авторизации
        current_url = driver.current_url
        page_title = driver.title
        logger.info(f"Текущий URL после ожидания: {current_url}")
        logger.info(f"Заголовок страницы: {page_title}")

        # Проверяем, изменился ли URL (признак успешной авторизации)
        if current_url != "https://eds.mosreg.ru/#login":
            logger.info("Авторизация успешна: URL изменился.")
        else:
            logger.error("Авторизация не прошла — URL не изменился.")

            # Дополнительная диагностика: ищем сообщения об ошибке на странице
            try:
                # Ищем элементы с текстами ошибок (разные возможные классы)
                error_selectors = [
                    ".error-message",
                    ".alert-danger",
                    ".text-danger",
                    "[role='alert']",
                    ".notification.error"
                ]
                for selector in error_selectors:
                    try:
                        error_element = driver.find_element(By.CSS_SELECTOR, selector)
                        error_text = error_element.text.strip()
                        if error_text:
                            logger.error(f"На странице обнаружено сообщение об ошибке: {error_text}")
                            break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Не удалось проверить сообщения об ошибке: {e}")

            # Проверяем наличие CAPTCHA (косвенный признак — специфические элементы)
            try:
                captcha_element = driver.find_element(
                    (By.XPATH, "//*[contains(text(), 'CAPTCHA') or contains(@id, 'captcha') or contains(@class, 'captcha')]")
                )
                if captcha_element.is_displayed():
                    logger.error("На странице обнаружена CAPTCHA — требуется ручное подтверждение.")
            except:
                pass  # CAPTCHA не найдена или не видна

        # 13. Дополнительная проверка: состояние кнопки после попытки авторизации
        try:
            submit_button_after = driver.find_element(By.CSS_SELECTOR, "button.lib-button.green")
            is_disabled_after = submit_button_after.get_attribute("disabled")
            logger.info(f"Состояние кнопки после попытки авторизации: disabled={is_disabled_after}")
        except Exception as e:
            logger.warning(f"Не удалось проверить состояние кнопки после авторизации: {e}")

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

