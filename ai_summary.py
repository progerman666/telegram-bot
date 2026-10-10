import requests

def summarize_applications(applications_text: str) -> str:
    """Генерирует сводку через локальную модель Ollama."""
    prompt = f"""Ты — ассистент менеджера проектов в digital-агентстве.
Сделай краткую сводку по заявкам за день.

Заявки:
{applications_text}

Формат сводки:
- Сколько всего заявок
- Основные темы
- Самые срочные/важные
- Что стоит сделать в первую очередь"""

    resp = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "llama3.2",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
    )
    return resp.json()["message"]["content"]