import os

os.makedirs("output", exist_ok=True)

dockerfile = """# Используем готовый образ Python
FROM python:3.11-slim

# Рабочая папка в контейнере
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Команда запуска бота
CMD ["python", "bot.py"]
"""

with open("output/Dockerfile", "w", encoding="utf-8") as f:
    f.write(dockerfile)

print("Dockerfile создан!")
print("Содержимое:")
print("-" * 40)
print(dockerfile)
print("-" * 40)