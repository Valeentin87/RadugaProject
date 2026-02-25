import csv
from typing import Dict, List, Tuple, Union
from create_bot import logger

# Тип для элементов кортежа
Record = Tuple[int, str, int]

# Тип для значения в словаре
StatisticValue = List[Union[int, Record]]

def save_statistic_to_csv(statistic_data: Dict[str, StatisticValue], file_path: str = 'data/statistic_data.csv') -> None:
    """
    Сохраняет статистические данные в CSV-файл.
    
    :param statistic_data: словарь с данными для сохранения
    :param file_path: путь к файлу для сохранения
    """
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            for key, value in statistic_data.items():
                # Записываем заголовок
                writer.writerow([key])
                
                # Записываем количество
                writer.writerow(['Количество:', value[0]])
                
                # Записываем записи
                for record in value[1:]:
                    writer.writerow(record)
                
                # Пустая строка между категориями
                writer.writerow([])
                
    except IOError as e:
        logger.errod(f"Ошибка при записи в файл: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")

def load_statistic_from_csv(file_path: str = 'data/statistic_data.csv') -> Dict[str, StatisticValue]:
    """
    Загружает статистические данные из CSV-файла.
    
    :param file_path: путь к файлу для загрузки
    :return: словарь с загруженными данными
    """
    try:
        statistic_data = {}
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            current_key = None
            current_values = []
            
            for row in reader:
                if not row:
                    # Пустая строка означает конец категории
                    if current_key:
                        statistic_data[current_key] = current_values
                        current_key = None
                        current_values = []
                    continue
                
                if len(row) == 1:
                    # Это заголовок категории
                    current_key = row[0]
                    continue
                
                if 'Количество:' in row[0]:
                    # Это количество
                    count = int(row[1])
                    current_values.append(count)
                    continue
                
                # Это запись
                record = (int(row[0]), row[1], int(row[2]))
                current_values.append(record)
            
            # Добавляем последнюю категорию
            if current_key:
                statistic_data[current_key] = current_values
                
        return statistic_data
    
    except FileNotFoundError:
        logger.error(f"Файл {file_path} не найден")
        return {}
    except IOError as e:
        logger.error(f"Ошибка при чтении файла: {e}")
        return {}
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        return {}