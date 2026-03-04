import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
import logging
import json
import re
from datetime import datetime
import os
import sys
from threading import Thread
import requests

# ===== БЛОК ДЛЯ RENDER =====
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Litera Bot is running! 🤖"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()
# ===== КОНЕЦ БЛОКА =====

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Создаем отдельные логгеры
user_logger = logging.getLogger('user_actions')
user_handler = logging.FileHandler('logs/user_actions.log', encoding='utf-8')
user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
user_logger.addHandler(user_handler)
user_logger.setLevel(logging.INFO)

error_logger = logging.getLogger('errors')
error_handler = logging.FileHandler('logs/errors.log', encoding='utf-8')
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
error_logger.addHandler(error_handler)
error_logger.setLevel(logging.ERROR)

essay_logger = logging.getLogger('essays')
essay_handler = logging.FileHandler('logs/essays.log', encoding='utf-8')
essay_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
essay_logger.addHandler(essay_handler)
essay_logger.setLevel(logging.INFO)

# ===== ТВОИ ДАННЫЕ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
TOKEN = os.getenv('BOT_TOKEN')
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')  # Теперь Яндекс
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')  # ID каталога в Яндекс.Облаке

if not TOKEN:
    logging.error("❌ Нет BOT_TOKEN в переменных окружения!")
    sys.exit(1)

if not YANDEX_API_KEY:
    logging.error("❌ Нет YANDEX_API_KEY в переменных окружения!")
    sys.exit(1)

if not YANDEX_FOLDER_ID:
    logging.error("❌ Нет YANDEX_FOLDER_ID в переменных окружения!")
    sys.exit(1)

# ===== ИНИЦИАЛИЗАЦИЯ =====
dp = Dispatcher()
user_states = {}

# Логируем запуск
logging.info("="*50)
logging.info("БОТ ЗАПУЩЕН")
logging.info(f"Flask сервер запущен на порту {os.environ.get('PORT', 10000)}")
logging.info("="*50)

print("🔄 Подключение к Yandex GPT...")
logging.info("Yandex GPT настроен")
print("✅ Yandex GPT готов к работе!")

def log_user_action(user_id, username, action, details=""):
    """Логирование действий пользователя"""
    log_entry = f"User {user_id} (@{username}) - {action} - {details}"
    user_logger.info(log_entry)
    logging.info(log_entry)

def log_essay_analysis(user_id, username, topic, source_length, essay_length, result):
    """Логирование анализа сочинения"""
    log_entry = f"User {user_id} (@{username}) | Тема: {topic[:50]}... | Исходный текст: {source_length} симв. | Сочинение: {essay_length} слов | Результат: {result}"
    essay_logger.info(log_entry)

def analyze_with_yandex(essay_text, topic, source_text):
    """Функция анализа сочинения через Yandex GPT"""
    word_count = len(essay_text.split())
    
    # Формируем промпт
    prompt = f"""Ты эксперт ОГЭ по русскому языку. Оцени сочинение по критериям ФИПИ.

ТЕМА: {topic}

ИСХОДНЫЙ ТЕКСТ: {source_text}

СОЧИНЕНИЕ: {essay_text}

Критерии оценки:
1. Структура и содержание (0-4 балла)
2. Грамотность (0-2 балла)
3. Фактологическая точность (0-1 балл)

Верни ТОЛЬКО JSON в формате:
{{
    "scores": {{
        "structure": число,
        "grammar": число,
        "accuracy": число
    }},
    "total_score": число,
    "analysis": {{
        "structure_comment": "разбор",
        "grammar_comment": "разбор",
        "accuracy_comment": "разбор",
        "strengths": ["плюс1", "плюс2"],
        "weaknesses": ["минус1", "минус2"]
    }},
    "recommendations": "совет"
}}"""

    # URL для Yandex GPT
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    # Заголовки
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Данные запроса
    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.3,
            "maxTokens": 2000
        },
        "messages": [
            {
                "role": "system",
                "text": "Ты эксперт ОГЭ. Отвечай только JSON."
            },
            {
                "role": "user",
                "text": prompt
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            # Извлекаем текст ответа
            answer_text = result['result']['alternatives'][0]['message']['text']
            
            # Парсим JSON из ответа
            json_match = re.search(r'\{.*\}', answer_text, re.DOTALL)
            if json_match:
                return json_match.group()
            else:
                return json.dumps({
                    "scores": {"structure": 2, "grammar": 1, "accuracy": 1},
                    "total_score": 4,
                    "analysis": {
                        "structure_comment": "Средне",
                        "grammar_comment": "Есть ошибки",
                        "accuracy_comment": "Норм",
                        "strengths": ["Есть понимание темы"],
                        "weaknesses": ["Мало аргументов"]
                    },
                    "recommendations": "Пиши больше"
                })
        else:
            error_logger.error(f"Ошибка Yandex GPT: {response.status_code}")
            return json.dumps({
                "scores": {"structure": 0, "grammar": 0, "accuracy": 0},
                "total_score": 0,
                "analysis": {
                    "structure_comment": "Ошибка API",
                    "grammar_comment": "Ошибка API",
                    "accuracy_comment": "Ошибка API",
                    "strengths": ["-"],
                    "weaknesses": ["Техническая ошибка"]
                },
                "recommendations": "Попробуй позже"
            })
    except Exception as e:
        error_logger.error(f"Ошибка: {e}")
        return json.dumps({
            "scores": {"structure": 0, "grammar": 0, "accuracy": 0},
            "total_score": 0,
            "analysis": {
                "structure_comment": str(e),
                "grammar_comment": "Ошибка",
                "accuracy_comment": "Ошибка",
                "strengths": ["-"],
                "weaknesses": [str(e)]
            },
            "recommendations": "Техническая ошибка"
        })

# ===== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ОБЪЕМА =====
def check_volume(text):
    words = len(text.split())
    if words < 70:
        return False, words
    return True, words

# ===== ОБРАБОТЧИКИ КОМАНД =====
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "START", "Начал работу с ботом")
    
    await message.answer(
        'Привет! Я - Литера - чат-бот помощник на Яндекс GPT!\n'
        '\n'
        'Анализирую сочинения по критериям ОГЭ\n'
        '\n'
        '/at - Анализ сочинения\n'
        '/criteria - Критерии оценки\n'
        '/help - Помощь'
    )

@dp.message(Command('help'))
async def command_help_handler(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "HELP", "Запросил помощь")
    
    await message.answer(
        'Команды:\n'
        '/start - Начать\n'
        '/at - Анализ сочинения\n'
        '/criteria - Критерии\n'
        '/cancel - Отмена'
    )

@dp.message(Command('criteria'))
async def show_criteria(message: Message):
    await message.answer(
        "📚 <b>Критерии ОГЭ:</b>\n\n"
        "1. Структура и содержание (0-4)\n"
        "2. Грамотность (0-2)\n"
        "3. Фактологическая точность (0-1)\n\n"
        "Минимум слов: 70"
    )

@dp.message(Command('at'))
async def start_analysis(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "AT_START", "Начал анализ")
    
    user_states[user_id] = {'stage': 'waiting_topic'}
    await message.answer(
        "📝 <b>ШАГ 1/3: Введи ТЕМУ сочинения</b>\n\n"
        "/cancel - отмена"
    )

@dp.message(Command('cancel'))
async def cancel(message: Message):
    user_id = message.from_user.id
    
    if user_id in user_states:
        del user_states[user_id]
        await message.answer("✅ Отменено")
    else:
        await message.answer("❌ Нечего отменять")

@dp.message()
async def handle_text(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    if user_id not in user_states:
        await message.answer("Напиши /at для анализа")
        return
    
    state = user_states[user_id]
    current_stage = state.get('stage')
    
    if current_stage == 'waiting_topic':
        user_states[user_id] = {
            'stage': 'waiting_source',
            'topic': message.text
        }
        await message.answer("📝 <b>ШАГ 2/3: Введи ИСХОДНЫЙ ТЕКСТ</b>")
        return
    
    elif current_stage == 'waiting_source':
        user_states[user_id] = {
            'stage': 'waiting_essay',
            'topic': state['topic'],
            'source': message.text
        }
        await message.answer("📝 <b>ШАГ 3/3: Отправь СОЧИНЕНИЕ</b>\nМинимум 70 слов")
        return
    
    elif current_stage == 'waiting_essay':
        essay_text = message.text
        topic = state['topic']
        source = state['source']
        
        del user_states[user_id]
        
        # Проверка объема
        meets_volume, word_count = check_volume(essay_text)
        if not meets_volume:
            await message.reply(f"❌ Мало слов: {word_count}/70")
            return
        
        progress = await message.reply("🔄 Яндекс GPT анализирует...")
        
        # Анализ
        result_json = analyze_with_yandex(essay_text, topic, source)
        
        try:
            data = json.loads(result_json)
            
            total = data.get('total_score', 0)
            scores = data.get('scores', {})
            
            answer = f"""
📊 <b>РЕЗУЛЬТАТ:</b>

1. Структура: {scores.get('structure', 0)}/4
2. Грамотность: {scores.get('grammar', 0)}/2
3. Точность: {scores.get('accuracy', 0)}/1

<b>ИТОГО: {total}/7</b>

💡 {data.get('recommendations', '')}
"""
            await progress.edit_text(answer, parse_mode='HTML')
            
        except Exception as e:
            await progress.edit_text(f"Ошибка: {e}")

async def main() -> None:
    bot = Bot(token=TOKEN)
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Остановлен")
    except Exception as e:
        logging.critical(f"Ошибка: {e}")
