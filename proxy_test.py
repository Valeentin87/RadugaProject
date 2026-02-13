from typing import List, Dict
import re

def parse_proxies_file(filename: str) -> List[Dict[str, int | str]]:
    """
    Парсит файл с данными прокси и возвращает список словарей с полями:
    - proxy_host (str)
    - proxy_port (int)
    - username (str)
    - password (str)

    Формат строки в файле: username:password@proxy_host:proxy_port


    Args:
        filename (str): имя файла с прокси‑данными в текущей директории


    Returns:
        List[Dict[str, int | str]]: список словарей с распарсенными данными прокси.
        Поле 'proxy_port' имеет тип int.

    Raises:
        FileNotFoundError: если файл не найден
        ValueError: если строка в файле имеет неверный формат или порт не является числом
    """
    proxies = []
    
    # Регулярное выражение для разбора строки прокси
    # Группы: username, password, host, port
    pattern = re.compile(
        r'^(?P<username>[^:]+):(?P<password>[^@]+)@(?P<proxy_host>[^:]+):(?P<proxy_port>\d+)$'
    )

    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                line = line.strip()
                if not line:  # пропускаем пустые строки
                    continue

                match = pattern.match(line)
                if not match:
                    raise ValueError(
                        f"Неверный формат строки {line_num}: '{line}'. "
                        "Ожидаемый формат: username:password@host:port"
                    )

                # Преобразуем порт в int
                try:
                    port = int(match.group('proxy_port'))
                except ValueError:
                    raise ValueError(
                        f"Порт в строке {line_num} не является числом: '{match.group('proxy_port')}'")


                proxies.append({
                    'proxy_host': match.group('proxy_host'),
                    'proxy_port': port,  # теперь int
                    'username': match.group('username'),
                    'password': match.group('password')
                })

    except FileNotFoundError:
        raise FileNotFoundError(f"Файл '{filename}' не найден в текущей директории.")

    except Exception as e:
        if isinstance(e, (ValueError, FileNotFoundError)):
            raise e
        else:
            raise Exception(f"Ошибка при обработке файла: {e}")


    return proxies