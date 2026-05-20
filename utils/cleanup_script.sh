#!/bin/bash

# Переход в нужную директорию
cd /home/developer/RadugaProject/data/worked_pages || {
    echo "Ошибка: не удалось перейти в директорию /home/developer/RadugaProject/data/worked_pages"
    exit 1
}

# Удаление файлов, начинающихся на "claims_info"
echo "Удаление файлов claims_info*..."
rm -f claims_info*

# Очистка лог‑файла (оставляем последние 100 строк)
LOG_FILE="/home/developer/RadugaProject/claims_control.log"
echo "Очистка лога $LOG_FILE (оставляем 100 последних строк)..."
if [ -f "$LOG_FILE" ]; then
    tail -n 100 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
else
    echo "Предупреждение: лог‑файл $LOG_FILE не найден"
fi

# Отключение службы
echo "Отключаем службу claims_control.service..."
sudo systemctl disable claims_control.service

# Остановка службы
echo "Останавливаем службу claims_control.service..."
sudo systemctl stop claims_control.service

# Удаление временных файлов и папок (пример для /tmp, можно расширить)
echo "Удаляем временные файлы и папки..."
sudo find /tmp -type f -atime +7 -delete
sudo find /tmp -type d -empty -delete

# Дополнительное удаление всего содержимого /tmp
echo "Выполняем sudo rm -rf /tmp/*..."
sudo rm -rf /tmp/*

# Завершение процессов Chrome
echo "Завершаем процессы Chrome..."
pkill -f chrome

# Запись информации о дисковом пространстве в лог
echo "Записываем информацию о дисковом пространстве в memory_usage.log..."
df -h >> /home/developer/memory_usage.log

# Включение службы
echo "Включаем службу claims_control.service..."
sudo systemctl enable claims_control.service

# Запуск службы
echo "Запускаем службу claims_control.service..."
sudo systemctl start claims_control.service

echo "Скрипт выполнен успешно."
