import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
import logging
from gigachat import GigaChat
import json
import re
from datetime import datetime
import os
import sys
from threading import Thread

# ===== БЛОК ДЛЯ RENDER (НЕ УДАЛЯТЬ!) =====
from flask import Flask
import threading

# Создаем Flask сервер
app = Flask(__name__)

@app.route('/')
def home():
    return "Litera Bot is running! 🤖"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Запуск Flask сервера"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Запускаем Flask в фоне
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

# ===== ДАННЫЕ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ =====
TOKEN = os.getenv('BOT_TOKEN')
GIGACHAT_CREDENTIALS = os.getenv('GIGACHAT_CREDENTIALS')

if not TOKEN:
    logging.error("❌ Нет BOT_TOKEN в переменных окружения!")
    sys.exit(1)

if not GIGACHAT_CREDENTIALS:
    logging.error("❌ Нет GIGACHAT_CREDENTIALS в переменных окружения!")
    sys.exit(1)

# ===== ИНИЦИАЛИЗАЦИЯ =====
dp = Dispatcher()
user_states = {}

# Логируем запуск
logging.info("="*50)
logging.info("БОТ ЗАПУЩЕН")
logging.info(f"Flask сервер запущен на порту {os.environ.get('PORT', 10000)}")
logging.info("="*50)

print("Идет загрузка моделей ☆ｏ(＞＜；)○  ")
try:
    giga = GigaChat(credentials=GIGACHAT_CREDENTIALS, verify_ssl_certs=False)
    logging.info("GigaChat успешно загружен")
    print("Модели готовы к работе☆ \(≧▽≦)/")
except Exception as e:
    logging.error(f"Ошибка загрузки GigaChat: {e}")
    print(f"❌ Ошибка загрузки GigaChat: {e}")
    sys.exit(1)

def log_user_action(user_id, username, action, details=""):
    """Логирование действий пользователя"""
    log_entry = f"User {user_id} (@{username}) - {action} - {details}"
    user_logger.info(log_entry)
    logging.info(log_entry)

def log_essay_analysis(user_id, username, topic, source_length, essay_length, result):
    """Логирование анализа сочинения"""
    log_entry = f"User {user_id} (@{username}) | Тема: {topic[:50]}... | Исходный текст: {source_length} симв. | Сочинение: {essay_length} слов | Результат: {result}"
    essay_logger.info(log_entry)

def analysis_with_gigachat(essay_text, topic, source_text):
    """Функция анализа сочинения"""
    word_count = len(essay_text.split())
    
    prompt = f"""Вы выступаете в роли независимого эксперта, оценивающего сочинения учеников, написанные в рамках Основного Государственного Экзамена (ОГЭ) по русскому языку на март 2026 года.

ТЕМА СОЧИНЕНИЯ:
{topic}

ИСХОДНЫЙ ТЕКСТ (на основе которого написано сочинение):
{source_text}

СОЧИНЕНИЕ УЧЕНИКА:
{essay_text}

Основные требования и критерии оценки:
1. ОБЪЁМ СОЧИНЕНИЯ:
   - Минимальный требуемый объём: не менее 70 слов (сейчас в сочинении {word_count} слов)
   - Если слов меньше 70 - автоматически 0 баллов за всю работу
   - Рекомендуемый объём: около 140 слов

2. СТРУКТУРА И СОДЕРЖАНИЕ (0-4 балла):
   - Соответствие содержания заявленной теме
   - Наличие введения с постановкой проблемы
   - Аргументированное раскрытие темы с опорой на исходный текст
   - Наличие личного мнения ученика
   - Четкое заключение

3. ГРАМОТНОСТЬ И РЕЧЕВОЕ ОФОРМЛЕНИЕ (0-2 балла):
   - Отсутствие грубых грамматических ошибок
   - Отсутствие пунктуационных ошибок
   - Соблюдение стилистических норм
   - Логичная последовательность изложения

4. ФАКТОЛОГИЧЕСКАЯ ТОЧНОСТЬ (0-1 балл):
   - Точность понимания исходного текста
   - Отсутствие фактических ошибок при работе с исходным текстом
   - Корректность цитирования исходного текста

Проведите экспертизу сочинения строго по критериям ФИПИ 2026 года, учитывая тему и исходный текст.

Верните ОТВЕТ СТРОГО в формате JSON:
{{
    "word_count": {word_count},
    "meets_volume": true/false,
    "scores": {{
        "structure": число от 0 до 4,
        "grammar": число от 0 до 2,
        "accuracy": число от 0 до 1
    }},
    "total_score": число,
    "max_possible": 7,
    "analysis": {{
        "structure_comment": "подробный разбор структуры, содержания и соответствия теме",
        "grammar_comment": "замечания по грамотности",
        "accuracy_comment": "оценка работы с исходным текстом",
        "strengths": ["сильная сторона 1", "сильная сторона 2"],
        "weaknesses": ["что нужно исправить 1", "что нужно исправить 2"]
    }},
    "topic_relevance": "насколько сочинение соответствует теме",
    "source_usage": "как использован исходный текст",
    "recommendations": "конкретные рекомендации по улучшению",
    "expert_conclusion": "итоговое заключение эксперта"
}}

Важно: Если слов меньше 70, то total_score = 0, и в заключении укажите причину.
"""
    
    try:
        response = giga.chat(prompt)
        result = response.choices[0].message.content
        logging.debug(f"Получен ответ от GigaChat: {result[:100]}...")
        return result
    except Exception as e:
        error_logger.error(f"Ошибка GigaChat: {e}")
        return f"Ошибка: {e}"

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
    
    await message.answer(f'Привет! Я - Литера - чат-бот помощник, который способен проанализировать твои сочинения и подобрать тебе книгу под настроение!\n'
    '\n'
    'Часть функций находится в разработке, на данный момент доступны функции анализа сочинения\n'
    '\n'
    'Список доступных команд:\n'
    '/help - Показать помощь\n'
    '/at - Анализ сочинения\n'
    '/iar - Интервью пользователя и рекомендация книг в соответствии(в разработке, недоступна)\n'
    '/criteria - подробные критерии\n')

@dp.message(Command('help'))
async def command_help_handler(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "HELP", "Запросил помощь")
    
    await message.answer(
        'Доступные команды:\n'
        '/start - Начать работу\n'
        '/help - помощь\n'
        '/at - Анализ сочинения\n'
        '/iar - Интервью пользователя и рекомендация книг в соответствии(в разработке, недоступна)\n'
        '/criteria - подробные критерии\n'
        '/dispach - вызов набора команд'
    )

@dp.message(Command('criteria'))
async def show_criteria(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "CRITERIA", "Запросил критерии оценивания")
    
    await message.answer(
        "<b>Критерии оценивания ОГЭ 2026 (ФИПИ):</b>\n\n"
        "<b>1. Структура и содержание (0-4 балла):</b>\n"
        "• Введение с проблемой\n"
        "• Аргументация\n"
        "• Личное мнение\n"
        "• Заключение\n\n"
        "<b>2. Грамотность (0-2 балла):</b>\n"
        "• Грамматические ошибки\n"
        "• Пунктуационные ошибки\n"
        "• Стилистика\n\n"
        "<b>3. Фактологическая точность (0-1 балл):</b>\n"
        "• Понимание текста\n"
        "• Отсутствие фактических ошибок\n\n"
        "<b>Важно!</b> Минимум 70 слов, иначе 0 баллов"
    )

@dp.message(Command('at'))
async def start_analysis(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "AT_START", "Начал процесс анализа сочинения")
    
    user_states[user_id] = {'stage': 'waiting_topic'}
    await message.answer(
        "📝 <b>ШАГ 1 ИЗ 3: Введи ТЕМУ сочинения</b>\n\n"
        "Напиши тему, которую нужно было раскрыть.\n"
        "Например: <i>'Почему важно сохранять память о войне?'</i>\n\n"
        "/cancel - отменить"
    )

@dp.message(Command('cancel'))
async def cancel(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    if user_id in user_states:
        stage = user_states[user_id].get('stage', 'unknown')
        log_user_action(user_id, username, "CANCEL", f"Отменил действие на этапе {stage}")
        del user_states[user_id]
        await message.answer("✅ Отменено")
    else:
        log_user_action(user_id, username, "CANCEL", "Попытка отмены без активного действия")
        await message.answer("❌ Нечего отменять")

@dp.message()
async def handle_text(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    if user_id not in user_states:
        log_user_action(user_id, username, "TEXT_IGNORED", f"Отправил текст без активной сессии: {message.text[:50]}...")
        await message.answer("Напиши /at для анализа сочинения")
        return
    
    state = user_states[user_id]
    current_stage = state.get('stage')
    
    if current_stage == 'waiting_topic':
        topic = message.text
        log_user_action(user_id, username, "STEP1_TOPIC", f"Получена тема: {topic[:50]}...")
        
        user_states[user_id] = {
            'stage': 'waiting_source',
            'topic': topic
        }
        await message.answer(
            "📝 <b>ШАГ 2 ИЗ 3: Введи ИСХОДНЫЙ ТЕКСТ</b>\n\n"
            "Напиши текст, на основе которого нужно написать сочинение.\n"
            "/cancel - отменить"
        )
        return
    
    elif current_stage == 'waiting_source':
        source = message.text
        log_user_action(user_id, username, "STEP2_SOURCE", f"Получен исходный текст: {len(source)} символов")
        
        user_states[user_id] = {
            'stage': 'waiting_essay',
            'topic': state['topic'],
            'source': source
        }
        await message.answer(
            "📝 <b>ШАГ 3 ИЗ 3: Отправь СОЧИНЕНИЕ</b>\n\n"
            "Минимум 70 слов.\n\n"
            "/cancel - отменить"
        )
        return
    
    elif current_stage == 'waiting_essay':
        essay_text = message.text
        topic = state['topic']
        source = state['source']
        
        log_user_action(user_id, username, "STEP3_ESSAY", f"Получено сочинение: {len(essay_text.split())} слов")
        
        del user_states[user_id]
        
        meets_volume, word_count = check_volume(essay_text)
        
        if not meets_volume:
            log_user_action(user_id, username, "VOLUME_FAIL", f"Недостаточный объем: {word_count} слов")
            await message.reply(
                f"❌ <b>Недостаточный объем!</b>\n\n"
                f"В твоем сочинении {word_count} слов.\n"
                f"Минимальный порог: 70 слов.\n\n"
                f"Согласно критериям ФИПИ, работа получает 0 баллов.",
                parse_mode='HTML'
            )
            return
        
        bot = message.bot
        await bot.send_chat_action(message.chat.id, 'typing')
        progress = await message.reply(
            f"🔄 Эксперт GigaChat анализирует сочинение ({word_count} слов)...\n"
            f"Оценка по критериям ФИПИ 2026..."
        )
        
        logging.info(f"Запуск анализа для пользователя {user_id}")
        result = analysis_with_gigachat(essay_text, topic, source)
        
        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                total = data.get('total_score', 0)
                
                log_essay_analysis(
                    user_id, username, topic, 
                    len(source), word_count, 
                    f"Баллы: {total}/7"
                )
                
                structure_score = data.get('scores', {}).get('structure', 0)
                grammar_score = data.get('scores', {}).get('grammar', 0)
                accuracy_score = data.get('scores', {}).get('accuracy', 0)
                
                bar_structure = "🟩" * structure_score + "⬜" * (4 - structure_score)
                bar_grammar = "🟩" * grammar_score + "⬜" * (2 - grammar_score)
                bar_accuracy = "🟩" * accuracy_score + "⬜" * (1 - accuracy_score)
                
                answer = f"""
📊 <b>ЭКСПЕРТНОЕ ЗАКЛЮЧЕНИЕ (ФИПИ 2026)</b>
{'='*40}

📝 <b>Объем:</b> {word_count} слов (минимум 70)

<b>1. Структура и содержание ({structure_score}/4)</b>
{bar_structure}
💬 {data.get('analysis', {}).get('structure_comment', 'Анализ выполнен')}

<b>2. Грамотность ({grammar_score}/2)</b>
{bar_grammar}
💬 {data.get('analysis', {}).get('grammar_comment', 'Анализ выполнен')}

<b>3. Фактологическая точность ({accuracy_score}/1)</b>
{bar_accuracy}
💬 {data.get('analysis', {}).get('accuracy_comment', 'Анализ выполнен')}

<b>ИТОГОВЫЙ БАЛЛ: {total}/7</b>

✨ <b>Сильные стороны:</b>
"""
                for strength in data.get('analysis', {}).get('strengths', []):
                    answer += f"✅ {strength}\n"
                
                answer += f"\n📌 <b>Что улучшить:</b>\n"
                for weakness in data.get('analysis', {}).get('weaknesses', []):
                    answer += f"• {weakness}\n"
                
                answer += f"""

💡 <b>Рекомендации:</b>
{data.get('recommendations', 'Продолжай работать над сочинениями!')}

🔍 <b>Заключение эксперта:</b>
{data.get('expert_conclusion', 'Сочинение проанализировано.')}
"""
                await progress.edit_text(answer, parse_mode='HTML')
                logging.info(f"Анализ завершен для пользователя {user_id}, баллы: {total}/7")
            else:
                logging.warning(f"Не удалось распарсить JSON для пользователя {user_id}")
                await progress.edit_text(f"📝 Результат анализа:\n\n{result}")
        except Exception as e:
            error_logger.error(f"Ошибка при обработке результата для пользователя {user_id}: {e}")
            await progress.edit_text(f"📝 Результат анализа:\n\n{result}")
        
        return

@dp.message(Command('dispach'))
async def dispach(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"
    
    log_user_action(user_id, username, "DISPACH", "Запросил список команд")
    
    await message.answer(
        "Набор команд:\n"
        "/help - помощь\n"
        "/criteria - Критерии оценивания\n"
        "/start - Запуск/Перезапуск бота\n"
        "/cancel - отмена действия\n"
        "/at - анализ текста\n"
        "/iar - Опрос и Рекомендации книг(недоступно, в разработке)"
    )

async def main() -> None:
    bot = Bot(token=TOKEN)
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        error_logger.critical(f"Критическая ошибка: {e}")
        logging.critical(f"Критическая ошибка: {e}")
