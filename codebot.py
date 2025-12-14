# AIQYNLEARN TELEGRAM BOT - Версия с Groq API и улучшенными тестами
# Скопируй ВЕСЬ этот код в новую ячейку Colab

print("📦 Установка библиотек...")
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "python-telegram-bot", "groq", "nest_asyncio"])
print("✅ Библиотеки установлены!")

import os
import json
import asyncio
import nest_asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from groq import Groq

nest_asyncio.apply()

# НАСТРОЙКИ
TELEGRAM_TOKEN = "8067223959:AAGxDhVnK3kbFuNkZsSlDEikF9aoAaiY9XA"
GROQ_API_KEY = "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"

# Инициализация Groq клиента
groq_client = Groq(api_key=GROQ_API_KEY)

LANGUAGE, AGE, INTERESTS, TEACHER_STYLE, LESSON_MODE, TOPIC, QUESTION_COUNT, QUESTION_TYPE, QUIZ_TYPE, CHATTING = range(10)
user_data = {}

def get_user_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'language': 'ru',
            'profile': {},
            'lessons': [],
            'active_lesson': None,
            'current_quiz': None,
            'quiz_answers': [],
            'quiz_current_question': 0,
            'quiz_total_questions': 0
        }
    return user_data[user_id]

def create_main_keyboard(lang='ru'):
    if lang == 'ru':
        return ReplyKeyboardMarkup([['👤 Профиль', '📚 Уроки'], ['➕ Новый урок', '❓ Помощь']], resize_keyboard=True)
    return ReplyKeyboardMarkup([['👤 Профиль', '📚 Сабактар'], ['➕ Жаңы сабак', '❓ Жардам']], resize_keyboard=True)

def create_learning_keyboard(lang='ru'):
    if lang == 'ru':
        return ReplyKeyboardMarkup([['🔄 Новый вопрос', '📊 Прогресс'], ['🏠 Главное меню']], resize_keyboard=True)
    return ReplyKeyboardMarkup([['🔄 Жаңы суроо', '📊 Прогресс'], ['🏠 Меню']], resize_keyboard=True)

def create_number_keyboard(lang='ru'):
    """Создает клавиатуру для выбора количества вопросов (1-10)"""
    buttons = []
    row = []

    for i in range(1, 11):
        button_text = f"{i}"
        callback_data = f"quiz_count_{i}"
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))

        if i % 5 == 0:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    if lang == 'ru':
        buttons.append([InlineKeyboardButton("❌ Отменить", callback_data='quiz_cancel')])
    else:
        buttons.append([InlineKeyboardButton("❌ Токтотуу", callback_data='quiz_cancel')])

    return InlineKeyboardMarkup(buttons)

def create_quiz_keyboard(options, lang='ru'):
    """Создает клавиатуру для теста с вариантами ответов"""
    buttons = []
    row = []

    for i, option in enumerate(options):
        letter = chr(65 + i)  # A, B, C, D
        button_text = f"{letter}) {option}"
        callback_data = f"quiz_answer_{letter}"

        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    if lang == 'ru':
        buttons.append([InlineKeyboardButton("🏁 Завершить тест досрочно", callback_data='quiz_finish')])
    else:
        buttons.append([InlineKeyboardButton("🏁 Тестти эрте аяктоо", callback_data='quiz_finish')])

    return InlineKeyboardMarkup(buttons)

async def call_groq_api(prompt, user_profile=None, lang='ru', mode=None):
    try:
        # Определяем язык системы
        system_lang = "Russian" if lang == 'ru' else "Kyrgyz"

        # Создаем системный промпт с методами обучения
        if user_profile:
            age = user_profile.get('age', 15)
            interests = ', '.join(user_profile.get('interests', [])) or 'разные темы'
            teacher_style = user_profile.get('teacherStyle', 'kind_mentor')

            # Методы обучения в зависимости от возраста
            learning_methods = ""
            if age <= 10:
                learning_methods = """ИСПОЛЬЗУЙ ПРОВЕРЕННЫЕ МЕТОДЫ ОБУЧЕНИЯ ДЛЯ ДЕТЕЙ:
1. МЕТОД КОНКРЕТНЫХ ПРИМЕРОВ - объясняй через игры, мультфильмы, сказки
2. МЕТОД ВИЗУАЛИЗАЦИИ - используй аналогии с игрушками, животными
3. ИГРОВОЙ МЕТОД - превращай обучение в игру
4. МЕТОД ПОВТОРЕНИЯ - повторяй ключевые моменты 3 раза разными словами
5. МЕТОД ЭМОЦИОНАЛЬНОЙ СВЯЗИ - связывай с чувствами и эмоциями ребенка"""

            elif age <= 15:
                learning_methods = """ИСПОЛЬЗУЙ ПРОВЕРЕННЫЕ МЕТОДЫ ОБУЧЕНИЯ ДЛЯ ПОДРОСТКОВ:
1. МЕТОД ПРОБЛЕМНОГО ОБУЧЕНИЯ - задавай провокационные вопросы
2. МЕТОД ПРОЕКТОВ - покажи практическое применение
3. МЕТОД ДИСКУССИИ - вовлекай в обсуждение
4. МЕТОД КЕЙСОВ - используй реальные жизненные ситуации
5. МЕТОД МОТИВАЦИИ - покажи, зачем это нужно в жизни"""

            else:
                learning_methods = """ИСПОЛЬЗУЙ ПРОВЕРЕННЫЕ МЕТОДЫ ОБУЧЕНИЯ ДЛЯ ВЗРОСЛЫХ:
1. МЕТОД АНАЛИЗА - разбирай тему на составляющие
2. МЕТОД СРАВНЕНИЯ - сравнивай с уже известными концепциями
3. МЕТОД ПРАКТИЧЕСКОГО ПРИМЕНЕНИЯ - покажи, как использовать
4. МЕТОД САМОСТОЯТЕЛЬНОГО ОТКРЫТИЯ - подводи к выводам через вопросы
5. МЕТОД МЕТАКОГНИЦИИ - учи думать о своем мышлении"""

            # Стили учителя
            styles = {
                'anime_sensei': 'Ты как мудрый аниме-сенсей. Объясняй через истории и притчи.' if lang == 'ru' else 'Сен акилелуу аниме-сенсайсың. Тарыхтар жана ырым-жырымдар аркылуу түшүндүр.',
                'strict_professor': 'Ты строгий профессор. Будь точным и требовательным.' if lang == 'ru' else 'Сен катуу профессорсуң. Так жана талапкер бол.',
                'kind_mentor': 'Ты добрый наставник. Поддерживай и хвали ученика.' if lang == 'ru' else 'Сен жылуу наставниксиң. Окуучуну колдо жана макта.',
                'sport_coach': 'Ты энергичный спортивный тренер. Мотивируй и вдохновляй.' if lang == 'ru' else 'Сен энергиялуу спорттук тренерсиң. Мотивде жана рухландыр.',
                'gangsta': 'Ты крутой учитель. Объясняй на современном сленге с юмором.' if lang == 'ru' else 'Сен салттуу мугалимсиң. Заманбап сленг менен күлкү менен түшүндүр.',
                'alien': 'Ты инопланетный учёный. Удивляй необычными фактами.' if lang == 'ru' else 'Сен инопланеталык илимпозсуң. Гайбаттуу фактылар менен таң калтыр.',
                'minimalist': 'Ты минималист. Говори кратко и по делу.' if lang == 'ru' else 'Сен минималистсиң. Кыска жана иш боюнча сүйлө.'
            }

            style_instruction = styles.get(teacher_style, styles['kind_mentor'])

            # Текст на нужном языке
            if lang == 'ru':
                interests_text = f"Интересы ученика: {interests}. Связывай объяснение с этими темами!"
                age_text = f"Ученику {age} лет."

                system_prompt = f"""Ты - AiqynLearn, персональный AI-учитель. Отвечай ТОЛЬКО на русском языке.
{age_text}
{interests_text}
{style_instruction}

{learning_methods}

ВАЖНЫЕ ПРАВИЛА:
1. Всегда говори на русском языке
2. Используй эмодзи для наглядности 🎯✨🤔
3. Объясняй через интересы ученика
4. Используй проверенные методы обучения выше
5. Будь терпеливым и поддерживающим
6. Задавай вопросы для проверки понимания
7. Объясняй сложное простыми словами"""
            else:
                interests_text = f"Окуучунун кызыкчылыктары: {interests}. Түшүндүрүүнү ушул темалар менен байланыштыр!"
                age_text = f"Окуучу {age} жашта."

                system_prompt = f"""Сен - AiqynLearn, жеке AI-мугалим. ЖОК гана кыргыз тилинде жооп бер.
{age_text}
{interests_text}
{style_instruction}

{learning_methods}

МААНИЛҮҮ ЭРЕЖЕЛЕР:
1. Ар дайым кыргыз тилинде сүйлө
2. Нагляддуулук үчүн эмодзилерди колдон 🎯✨🤔
3. Окуучунун кызыкчылыктары аркылуу түшүндүр
4. Жогоруда көрсөтүлгөн текшерилген үйрөтүү ыкмаларын колдон
5. Сабырдуу жана колдоочу бол
6. Түшүнүүнү текшерүү үчүн суроолор бериңиз
7. Кыйын нерсени жөнөкөй сөздөр менен түшүндүр"""
        else:
            if lang == 'ru':
                system_prompt = "Ты - AiqynLearn, персональный AI-учитель. Отвечай ТОЛЬКО на русском языке. Учи мыслить, задавай наводящие вопросы. Используй проверенные методы обучения."
            else:
                system_prompt = "Сен - AiqynLearn, жеке AI-мугалим. ЖОК гана кыргыз тилинде жооп бер. Ойлонууга үйрөт, жол көрсөтүүчү суроолор бер. Текшерилген үйрөтүү ыкмаларын колдон."

        # Вызываем Groq API
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            top_p=0.9
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Ошибка Groq API: {e}")
        return "Извините, произошла ошибка при генерации ответа. Попробуйте ещё раз!" if lang == 'ru' else "Кечиресиз, жоопту түзүүдө ката кетти. Дагы бир жолу аракет кылыңыз!"

async def parse_quiz_response(quiz_text, lang='ru'):
    """Парсит ответ от ИИ для создания структурированного теста"""
    try:
        lines = quiz_text.split('\n')
        questions = []
        current_question = None

        for line in lines:
            line = line.strip()

            # Начало нового вопроса
            if line.startswith(('❓', '?')) or 'Вопрос' in line or 'Суроо' in line:
                if current_question:
                    questions.append(current_question)

                current_question = {
                    'text': line.replace('❓', '').replace('?', '').strip(),
                    'options': [],
                    'correct_answer': None
                }

            # Вариант ответа с буквой
            elif line.startswith(('А)', 'Б)', 'В)', 'Г)', 'A)', 'B)', 'C)', 'D)')):
                option_text = line[2:].strip()
                letter = line[0]
                current_question['options'].append((letter, option_text))

            # Правильный ответ
            elif 'правильный' in line.lower() or 'туура' in line.lower() or 'correct' in line.lower():
                for letter in ['А', 'Б', 'В', 'Г', 'A', 'B', 'C', 'D']:
                    if letter in line:
                        current_question['correct_answer'] = letter
                        break

        if current_question:
            questions.append(current_question)

        return questions

    except Exception as e:
        print(f"Ошибка парсинга теста: {e}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)

    welcome_text = f"👋 Привет, {update.effective_user.first_name}!\n\n🎯 *Добро пожаловать в AiqynLearn!*\n\nЯ - твой персональный AI-учитель.\n\nВыбери язык:"
    keyboard = [[InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru'), InlineKeyboardButton("🇰🇬 Кыргызча", callback_data='lang_ky')]]

    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    return LANGUAGE

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    if lang == 'ru':
        help_text = """*🤖 Помощь по AiqynLearn*

*Основные команды:*
/start - Начать работу
/profile - Мой профиль
/lessons - Мои уроки
/newlesson - Новый урок
/help - Эта справка

*Режимы обучения:*
📚 Объяснение - детальное объяснение темы
💪 Практика - задачи для решения
🎯 Тест - проверка знаний с кнопками

*Как использовать:*
1. Создайте профиль
2. Выберите тему
3. Начните обучение
4. Задавайте вопросы

Есть вопросы? Пишите!"""
    else:
        help_text = """*🤖 AiqynLearn жардамы*

*Негизги буйруктар:*
/start - Баштоо
/profile - Профиль
/lessons - Сабактар
/newlesson - Жаңы сабак
/help - Жардам

*Үйрөнүү режимдери:*
📚 Түшүндүрүү - теманы деталдуу түшүндүрүү
💪 Практика - чечүүгө маселелер
🎯 Тест - баскычтар менен билимди текшерүү

*Колдонуу:*
1. Профиль түзүңүз
2. Тема тандаңыз
3. Үйрөнүүнү баштаңыз
4. Суроо бериңиз

Суроолоруңуз барбы? Жазыңыз!"""

    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=create_main_keyboard(lang))

async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = query.data.split('_')[1]
    user['language'] = lang

    if lang == 'ru':
        await query.edit_message_text("🇷🇺 Русский выбран!")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="*Сколько тебе лет?*\n\nНапиши свой возраст (от 5 до 100):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await query.edit_message_text("🇰🇬 Кыргызча тандалды!")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="*Жашың канча?*\n\nЖашыңызды жазыңыз (5тен 100гө чейин):",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

    return AGE

async def handle_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    try:
        age = int(update.message.text)
        if age < 5 or age > 100:
            raise ValueError

        user['profile']['age'] = age

        if lang == 'ru':
            interests = [
                ["⚽ Спорт", "🎮 Игры"],
                ["🎬 Фильмы", "🎵 Музыка"],
                ["🧪 Наука", "💻 Технологии"],
                ["📚 Книги", "🎨 Искусство"],
                ["🌌 Космос", "🐉 Фэнтези"],
                ["✅ Готово"]
            ]
            text = "*Отлично! Что тебе интересно?*\n\nВыбери свои интересы (можно несколько):\n\nЭто поможет мне объяснять темы через то, что тебе нравится!"
        else:
            interests = [
                ["⚽ Спорт", "🎮 Оюндар"],
                ["🎬 Тасмалар", "🎵 Музыка"],
                ["🧪 Илим", "💻 Технологиялар"],
                ["📚 Китептер", "🎨 Көркөм өнөр"],
                ["🌌 Космос", "🐉 Фэнтези"],
                ["✅ Даяр"]
            ]
            text = "*Жакшы! Сизге эмне кызык?*\n\nКызыкчылыктарыңызды тандаңыз (бир нечесин):"

        user['profile']['interests'] = []
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(interests, resize_keyboard=True))
        return INTERESTS
    except ValueError:
        error_msg = "Пожалуйста, введи реальный возраст от 5 до 100:" if lang == 'ru' else "Туура жаш жазыңыз (5тен 100гө чейин):"
        await update.message.reply_text(error_msg)
        return AGE

async def handle_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    text = update.message.text

    if text in ["✅ Готово", "✅ Даяр"]:
        if lang == 'ru':
            styles = [
                ["👨‍🏫 Аниме-сенсей", "📚 Строгий профессор"],
                ["🤝 Добрый наставник", "🏃 Спортивный тренер"],
                ["😎 Крутой учитель", "👽 Инопланетный учёный"],
                ["🎯 Минималист", "✅ Завершить"]
            ]
            text = "*Выбери стиль своего учителя:*\n\nКаким ты хочешь видеть своего AI-учителя?"
        else:
            styles = [
                ["👨‍🏫 Аниме-сенсей", "📚 Катуу профессор"],
                ["🤝 Жылуу наставник", "🏃 Спорттук тренер"],
                ["😎 Салттуу мугалим", "👽 Инопланеталык илимпоз"],
                ["🎯 Минималист", "✅ Бүтүрүү"]
            ]
            text = "*Өзүңүздүн мугалимиңиздин стилин тандаңыз:*\n\nAI-мугалимиңиз кандай болушун каалайсыз?"

        user['profile']['teacherStyle'] = None
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardMarkup(styles, resize_keyboard=True))
        return TEACHER_STYLE

    if text not in user['profile']['interests']:
        user['profile']['interests'].append(text)

    current = ', '.join(user['profile']['interests'])
    if lang == 'ru':
        reply = f"✅ Добавлено: *{text}*\n\nТекущие интересы: {current}\n\nВыбери ещё или нажми 'Готово'"
    else:
        reply = f"✅ Кошулду: *{text}*\n\nАзыркы кызыкчылыктар: {current}\n\nДагы тандаңыз же 'Даяр' басыңыз"

    await update.message.reply_text(reply, parse_mode='Markdown')
    return INTERESTS

async def handle_teacher_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    text = update.message.text

    style_map = {
        '👨‍🏫 Аниме-сенсей': 'anime_sensei',
        '📚 Строгий профессор': 'strict_professor',
        '📚 Катуу профессор': 'strict_professor',
        '🤝 Добрый наставник': 'kind_mentor',
        '🤝 Жылуу наставник': 'kind_mentor',
        '🏃 Спортивный тренер': 'sport_coach',
        '🏃 Спорттук тренер': 'sport_coach',
        '😎 Крутой учитель': 'gangsta',
        '😎 Салттуу мугалим': 'gangsta',
        '👽 Инопланетный учёный': 'alien',
        '👽 Инопланеталык илимпоз': 'alien',
        '🎯 Минималист': 'minimalist'
    }

    if text in ["✅ Завершить", "✅ Бүтүрүү"]:
        profile = user['profile']

        if not profile.get('teacherStyle'):
            profile['teacherStyle'] = 'kind_mentor'

        if lang == 'ru':
            caption = f"""🎉 *Профиль успешно создан!*

👤 *Твои данные:*
• 🎂 Возраст: {profile['age']} лет
• ❤️ Интересы: {', '.join(profile.get('interests', ['Разные темы']))}
• 👨‍🏫 Стиль учителя: {text if text not in ['✅ Завершить', '✅ Бүтүрүү'] else 'Добрый наставник'}

Теперь ты готов к обучению!
Выбери действие из меню ниже:"""
        else:
            caption = f"""🎉 *Профиль ийгиликтүү түзүлдү!*

👤 *Сиздин маалыматтарыңыз:*
• 🎂 Жаш: {profile['age']} жаш
• ❤️ Кызыкчылыктар: {', '.join(profile.get('interests', ['Ар кандай темалар']))}
• 👨‍🏫 Мугалим стили: {text if text not in ['✅ Завершить', '✅ Бүтүрүү'] else 'Жылуу наставник'}

Эми сиз үйрөнүүгө даярсыз!
Төмөндөгү менюдан аракет тандаңыз:"""

        await update.message.reply_text(
            caption,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard(lang)
        )

        return ConversationHandler.END

    user['profile']['teacherStyle'] = style_map.get(text, 'kind_mentor')

    current_style = text
    if lang == 'ru':
        reply = f"✅ Выбран стиль: *{current_style}*\n\nОтличный выбор! Нажми '✅ Завершить' чтобы закончить создание профиля."
    else:
        reply = f"✅ Тандалды: *{current_style}*\n\nЖакшы тандоо! '✅ Бүтүрүү' басыңыз."

    await update.message.reply_text(reply, parse_mode='Markdown')
    return TEACHER_STYLE

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    profile = user.get('profile', {})

    if not profile:
        msg = "У тебя ещё нет профиля. Используй /start чтобы создать его!" if lang == 'ru' else "Профиль жок. Түзүү үчүн /start колдонуңуз!"
        await update.message.reply_text(msg, reply_markup=create_main_keyboard(lang))
        return

    style_display_ru = {
        'anime_sensei': '👨‍🏫 Аниме-сенсей',
        'strict_professor': '📚 Строгий профессор',
        'kind_mentor': '🤝 Добрый наставник',
        'sport_coach': '🏃 Спортивный тренер',
        'gangsta': '😎 Крутой учитель',
        'alien': '👽 Инопланетный учёный',
        'minimalist': '🎯 Минималист'
    }

    style_display_ky = {
        'anime_sensei': '👨‍🏫 Аниме-сенсей',
        'strict_professor': '📚 Катуу профессор',
        'kind_mentor': '🤝 Жылуу наставник',
        'sport_coach': '🏃 Спорттук тренер',
        'gangsta': '😎 Салттуу мугалим',
        'alien': '👽 Инопланеталык илимпоз',
        'minimalist': '🎯 Минималист'
    }

    style_display = style_display_ru if lang == 'ru' else style_display_ky
    teacher_style = style_display.get(profile.get('teacherStyle', 'kind_mentor'), 'Не выбран')

    if lang == 'ru':
        text = f"""👤 *Твой профиль*

*Основная информация:*
• 🎂 Возраст: {profile.get('age', 'Не указан')} лет
• ❤️ Интересы: {', '.join(profile.get('interests', ['Не указаны']))}
• 👨‍🏫 Стиль учителя: {teacher_style}

*Статистика:*
• 📚 Всего уроков: {len(user.get('lessons', []))}
• 🏆 Активных уроков: {1 if user.get('active_lesson') else 0}
• 🎯 Пройдено тестов: {len([l for l in user.get('lessons', []) if l.get('type') == 'quiz'])}"""
    else:
        text = f"""👤 *Сиздин профиль*

*Негизги маалыматтар:*
• 🎂 Жаш: {profile.get('age', 'Көрсөтүлгөн эмес')} жаш
• ❤️ Кызыкчылыктар: {', '.join(profile.get('interests', ['Көрсөтүлгөн эмес']))}
• 👨‍🏫 Мугалим стили: {teacher_style}

*Статистика:*
• 📚 Жалпы сабактар: {len(user.get('lessons', []))}
• 🏆 Активдүү сабактар: {1 if user.get('active_lesson') else 0}
• 🎯 Өткөн тесттер: {len([l for l in user.get('lessons', []) if l.get('type') == 'quiz'])}"""

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=create_main_keyboard(lang))

async def new_lesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    if not user.get('profile'):
        msg = "Сначала создай профиль через /start!" if lang == 'ru' else "Алгач /start менен профиль түзүңүз!"
        await update.message.reply_text(msg, reply_markup=create_main_keyboard(lang))
        return

    if lang == 'ru':
        text = "*Выбери режим обучения:*\n\nКак ты хочешь изучать новую тему?"
        buttons = [
            [InlineKeyboardButton("📚 Объяснение", callback_data='mode_explanation')],
            [InlineKeyboardButton("💪 Практика", callback_data='mode_practice')],
            [InlineKeyboardButton("🎯 Тест", callback_data='mode_quiz')]
        ]
    else:
        text = "*Үйрөнүү режимин тандаңыз:*\n\nЖаңы теманы кандай үйрөнгүңүз келет?"
        buttons = [
            [InlineKeyboardButton("📚 Түшүндүрүү", callback_data='mode_explanation')],
            [InlineKeyboardButton("💪 Практика", callback_data='mode_practice')],
            [InlineKeyboardButton("🎯 Тест", callback_data='mode_quiz')]
        ]

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    return LESSON_MODE

async def handle_lesson_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    mode = query.data.split('_')[1]

    if 'creating_lesson' not in user:
        user['creating_lesson'] = {}
    user['creating_lesson']['mode'] = mode

    # Если выбран тест, спрашиваем количество вопросов
    if mode == 'quiz':
        if lang == 'ru':
            text = "*Сколько вопросов хочешь в тесте?*\n\nВыбери количество (от 1 до 10):"
        else:
            text = "*Тестте канча суроо болсун?*\n\nСанды тандаңыз (1ден 10го чейин):"

        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=create_number_keyboard(lang))
        return QUESTION_COUNT
    else:
        mode_names = {
            'explanation': '📚 Объяснение' if lang == 'ru' else '📚 Түшүндүрүү',
            'practice': '💪 Практика',
            'quiz': '🎯 Тест'
        }

        if lang == 'ru':
            text = f"""✅ *Выбран режим: {mode_names[mode]}*

Теперь напиши *тему урока*:

*Примеры тем:*
• Законы Ньютона
• Фотосинтез растений
• Дроби в математике
• Великая Отечественная война
• Основы программирования на Python

Напиши свою тему урока:"""
        else:
            text = f"""✅ *Тандалды: {mode_names[mode]}*

Эми *сабактын темасын* жазыңыз:

*Темалардын мисалдары:*
• Ньютондун мыйзамдары
• Өсүмдүктөрдүн фотосинтези
• Математикада бөлчөктөр
• Улуу Ата Мекендик согуш
• Python программалоонун негиздери

Өз темаңызды жазыңыз:"""

        await query.edit_message_text(text, parse_mode='Markdown')
        return TOPIC

async def handle_question_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора количества вопросов"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    if query.data == 'quiz_cancel':
        # Возвращаемся к выбору режима
        return await new_lesson_command(update, context)

    count = int(query.data.split('_')[2])

    # Сохраняем количество вопросов
    if 'creating_lesson' not in user:
        user['creating_lesson'] = {}
    user['creating_lesson']['question_count'] = count

    # Спрашиваем тему
    if lang == 'ru':
        text = f"""✅ *Выбрано {count} вопросов*

Теперь напиши *тему теста*:

*Примеры тем для теста:*
• Законы Ньютона
• Фотосинтез растений
• Дроби в математике
• Великая Отечественная война
• Основы программирования на Python

Напиши тему для теста:"""
    else:
        text = f"""✅ *{count} суроо тандалды*

Эми *тестин темасын* жазыңыз:

*Тест үчүн темалардын мисалдары:*
• Ньютондун мыйзамдары
• Өсүмдүктөрдүн фотосинтези
• Математикада бөлчөктөр
• Улуу Ата Мекендик согуш
• Python программалоонун негиздери

Тесттин темасын жазыңыз:"""

    await query.edit_message_text(text, parse_mode='Markdown')
    return TOPIC

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    topic = update.message.text

    if len(topic) < 3:
        error = "❌ Тема слишком короткая! Напиши минимум 3 символа." if lang == 'ru' else "❌ Тема кыска! Кеминде 3 символ жазыңыз."
        await update.message.reply_text(error)
        return TOPIC

    # Сохраняем тему
    if 'creating_lesson' not in user:
        user['creating_lesson'] = {}
    user['creating_lesson']['topic'] = topic

    # Создаем урок
    loading_text = "⏳ *Создаю персональный урок...*\n\nAI анализирует твой профиль и подбирает материал!" if lang == 'ru' else "⏳ *Жеке сабак түзүлүүдө...*\n\nAI профилиңизди анализдеп, материалды тандап жатат!"
    msg = await update.message.reply_text(loading_text, parse_mode='Markdown')

    lesson_data = user.get('creating_lesson', {})
    lesson_mode = lesson_data.get('mode', 'explanation')
    question_count = lesson_data.get('question_count', 5)
    topic_text = lesson_data.get('topic', '')

    # Создаем промпт в зависимости от режима
    profile = user.get('profile', {})
    age = profile.get('age', 15)
    interests = profile.get('interests', [])
    teacher_style = profile.get('teacherStyle', 'kind_mentor')

    if lang == 'ru':
        context_info = f"""
КОНТЕКСТ УЧЕНИКА:
- Возраст: {age} лет
- Интересы: {', '.join(interests) if interests else 'разные темы'}
- Стиль обучения: {teacher_style}

ТЕМА УРОКА: {topic_text}
"""
    else:
        context_info = f"""
ОКУУЧУНУН КОНТЕКСТИ:
- Жаш: {age} жаш
- Кызыкчылыктар: {', '.join(interests) if interests else 'ар кандай темалар'}
- Үйрөнүү стили: {teacher_style}

САБАКТЫН ТЕМАСЫ: {topic_text}
"""

    if lesson_mode == 'explanation':
        if lang == 'ru':
            prompt = f"""{context_info}

ОБЪЯСНИ ТЕМУ "{topic_text}" ИСПОЛЬЗУЯ ПРОВЕРЕННЫЕ МЕТОДЫ ОБУЧЕНИЯ:

1. 🎯 Начни с простого определения - что это такое простыми словами?
2. 💡 Объясни ПОЧЕМУ эта тема важна в жизни/учебе
3. 📝 Приведи 2-3 конкретных примера из интересов ученика
4. ✨ Добавь интересный факт о теме
5. 🔗 Используй методы обучения соответствующие возрасту ученика
6. ❓ В конце задай 3 вопроса для проверки понимания

ВСЕ объяснения делай на русском языке!"""
        else:
            prompt = f"""{context_info}

"{topic_text}" темасын ТЕКШЕРИЛГЕН ҮЙРӨТҮҮ ЫКМАЛАРЫН КОЛДОНУП ТҮШҮНДҮР:

1. 🎯 Жөнөкөй аныктамадан башта - бул эмне жөнөкөй сөздөр менен?
2. 💡 Эмне үчүн бул тема жашоодо/окууда маанилүү экенин түшүндүр
3. 📝 Окуучунун кызыкчылыктарынан 2-3 конкреттүү мисал келтир
4. ✨ Тема боюнча кызыктуу факт кош
5. 🔗 Окуучунун жашына туура келген үйрөтүү ыкмаларын колдон
6. ❓ Аягында түшүнүүнү текшерүү үчүн 3 суроо бер

БААРДЫК түшүндүрмөлөрдү кыргыз тилинде жаз!"""

    elif lesson_mode == 'practice':
        if lang == 'ru':
            prompt = f"""{context_info}

СОЗДАЙ ПРАКТИЧЕСКОЕ ЗАДАНИЕ ПО ТЕМЕ "{topic_text}":

1. 📋 Кратко объясни концепцию (1-2 предложения)
2. 💪 Задача №1 - простая, с ПОЛНЫМ пошаговым решением
3. 🎯 Задача №2 - средней сложности, для самостоятельного решения
4. 💡 Подсказки ко второй задаче (если нужно)
5. ✅ Критерии правильного ответа
6. 🔗 Свяжи задачи с интересами ученика

Все на русском языке!"""
        else:
            prompt = f"""{context_info}

"{topic_text}" темасы боюнча ПРАКТИКАЛЫК ТАПШЫРМА ТҮЗ:

1. 📋 Концепцияны кыскача түшүндүр (1-2 сүйлөм)
2. 💪 Тапшырма №1 - жөнөкөй, ТОЛУК кадамдык чечим менен
3. 🎯 Тапшырма №2 - орточа татаалдыкта, өз алдынча чечүү үчүн
4. 💡 Экинчи тапшырма үчүн көрсөтмөлөр (керек болсо)
5. ✅ Туура жооптун критерийлери
6. 🔗 Тапшырмаларды окуучунун кызыкчылыктары менен байланыштыр

Баары кыргыз тилинде!"""

    else:  # quiz
        if lang == 'ru':
            prompt = f"""{context_info}

СОЗДАЙ ТЕСТ ПО ТЕМЕ "{topic_text}" из {question_count} вопросов:

ВАЖНО:
1. Создай РОВНО {question_count} вопросов
2. Каждый вопрос должен иметь 4 варианта ответа (A, B, C, D)
3. Только один вариант правильный
4. НЕ указывай правильные ответы в тексте
5. В конце напиши: "Правильные ответы: [буквы через запятую]"

Формат:
Вопрос 1: [текст вопроса]
A) [вариант А]
B) [вариант B]
C) [вариант C]
D) [вариант D]

[остальные вопросы]

Правильные ответы: A,B,C,D,A,B...

Сделай вопросы интересными и связанными с интересами ученика!
Все на русском языке!"""
        else:
            prompt = f"""{context_info}

"{topic_text}" темасы боюнча {question_count} суроодон турган ТЕСТ ТҮЗ:

МААНИЛҮҮ:
1. ТАК {question_count} суроо түз
2. Ар бир суроонун 4 жооп варианты болсун (A, B, C, D)
3. Жалгыз гана бир вариант туура болсун
4. Текстте туура жоопторду КӨРСӨТПӨ


Формат:
Суроо 1: [суроонун тексти]
A) [А варианты]
B) [B варианты]
C) [C варианты]
D) [D варианты]

[калган суроолор]


Суроолорду кызыктуу жана окуучунун кызыкчылыктары менен байланыштырылган кылыңыз!
Баары кыргыз тилинде!"""

    # Вызываем Groq API
    ai_response = await call_groq_api(prompt, profile, lang, lesson_mode)

    # Создаем объект урока
    new_lesson = {
        'id': str(datetime.now().timestamp()),
        'topic': topic_text,
        'type': lesson_mode,
        'question_count': question_count if lesson_mode == 'quiz' else None,
        'content': ai_response,
        'created': datetime.now().isoformat(),
        'progress': 0
    }

    if lesson_mode == 'quiz':
        # Парсим вопросы для теста с кнопками
        questions = await parse_quiz_response(ai_response, lang)
        if questions:
            new_lesson['questions'] = questions
            new_lesson['total_questions'] = len(questions)

            # Извлекаем правильные ответы из конца текста
            correct_answers = []
            if "Правильные ответы:" in ai_response:
                answers_line = ai_response.split("Правильные ответы:")[1].split("\n")[0].strip()
                correct_answers = [ans.strip() for ans in answers_line.split(",")]
            elif "Туура жооптор:" in ai_response:
                answers_line = ai_response.split("Туура жооптор:")[1].split("\n")[0].strip()
                correct_answers = [ans.strip() for ans in answers_line.split(",")]

            # Применяем правильные ответы к вопросам
            for i, question in enumerate(questions):
                if i < len(correct_answers):
                    question['correct_answer'] = correct_answers[i]

            # Сохраняем тест в активный
            user['current_quiz'] = {
                'questions': questions,
                'current_question': 0,
                'answers': [],
                'lesson_id': new_lesson['id'],
                'question_count': question_count
            }

    if 'lessons' not in user:
        user['lessons'] = []
    user['lessons'].append(new_lesson)
    user['active_lesson'] = new_lesson

    mode_emoji = {'explanation': '📚', 'practice': '💪', 'quiz': '🎯'}
    mode_names = {
        'explanation': 'Объяснение' if lang == 'ru' else 'Түшүндүрүү',
        'practice': 'Практика',
        'quiz': 'Тест'
    }

    if lang == 'ru':
        caption = f"""✅ *Урок успешно создан!*

{mode_emoji[lesson_mode]} *Режим:* {mode_names[lesson_mode]}
📖 *Тема:* {topic_text}
👤 *Персонализация:* ✅ (возраст {age}, интересы: {', '.join(interests[:2]) if interests else 'учтены'})"""

        if lesson_mode == 'quiz':
            caption += f"\n\n🎯 *Тест создан!* {question_count} вопросов с вариантами ответов."

        caption += f"""

────────────────
{ai_response}
────────────────

💬 *Что дальше?*"""

        if lesson_mode == 'quiz':
            caption += "\n• Нажми '🎯 Начать тест' чтобы начать тест с кнопками"
        else:
            caption += "\n• Задавай вопросы по теме"

        caption += "\n• Попроси объяснить подробнее\n• Или создай новый урок"

    else:
        caption = f"""✅ *Сабак түзүлдү!*

{mode_emoji[lesson_mode]} *Режим:* {mode_names[lesson_mode]}
📖 *Тема:* {topic_text}
👤 *Жекечелөө:* ✅ (жаш {age}, кызыкчылыктар: {', '.join(interests[:2]) if interests else 'эске алынган'})"""

        if lesson_mode == 'quiz':
            caption += f"\n\n🎯 *Тест түзүлдү!* {question_count} суроо жооп варианттары менен."

        caption += f"""

────────────────
{ai_response}
────────────────

💬 *Эми эмне кылабыз?*"""

        if lesson_mode == 'quiz':
            caption += "\n• Баскычтар менен тестти баштоо үчүн '🎯 Тестти баштоо' басыңыз"
        else:
            caption += "\n• Тема боюнча суроо бериңиз"

        caption += "\n• Толугураак түшүндүрүүнү сураңыз\n• Же жаңы сабак түзүңүз"

    if len(caption) > 4000:
        parts = []
        current_part = ""
        lines = caption.split('\n')

        for line in lines:
            if len(current_part) + len(line) + 1 < 4000:
                current_part += line + '\n'
            else:
                parts.append(current_part)
                current_part = line + '\n'

        if current_part:
            parts.append(current_part)

        await msg.edit_text(parts[0], parse_mode='Markdown')
        for part in parts[1:]:
            await update.message.reply_text(part, parse_mode='Markdown')
    else:
        await msg.edit_text(caption, parse_mode='Markdown')

    # Создаем клавиатуру в зависимости от типа урока
    if lesson_mode == 'quiz':
        quiz_keyboard = ReplyKeyboardMarkup([
            ['🎯 Начать тест' if lang == 'ru' else '🎯 Тестти баштоо', '📊 Прогресс'],
            ['🏠 Главное меню' if lang == 'ru' else '🏠 Меню']
        ], resize_keyboard=True)
        await update.message.reply_text(
            "🎓 Готов к обучению! Нажми '🎯 Начать тест' чтобы начать тест с кнопками:" if lang == 'ru' else "🎓 Үйрөнүүгө даярмын! Баскычтар менен тестти баштоо үчүн '🎯 Тестти баштоо' басыңыз:",
            reply_markup=quiz_keyboard
        )
    else:
        await update.message.reply_text(
            "🎓 Готов к обучению! Используй кнопки ниже:" if lang == 'ru' else "🎓 Үйрөнүүгө даярмын! Төмөнкү баскычтарды колдонуңуз:",
            reply_markup=create_learning_keyboard(lang)
        )

    # Очищаем временные данные
    if 'creating_lesson' in user:
        del user['creating_lesson']

    return CHATTING

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает тест с кнопками"""
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    if not user.get('current_quiz'):
        msg = "Нет активного теста. Создайте новый тест!" if lang == 'ru' else "Активдүү тест жок. Жаңы тест түзүңүз!"
        await update.message.reply_text(msg, reply_markup=create_learning_keyboard(lang))
        return CHATTING

    quiz = user['current_quiz']
    questions = quiz['questions']
    current_idx = quiz['current_question']

    if current_idx >= len(questions):
        # Тест завершен
        await finish_quiz(update, context)
        return CHATTING

    # Показываем текущий вопрос
    question = questions[current_idx]

    if lang == 'ru':
        question_text = f"""🎯 *Тест: Вопрос {current_idx + 1} из {len(questions)}*

{question['text']}"""
    else:
        question_text = f"""🎯 *Тест: Суроо {current_idx + 1} {len(questions)}дан*

{question['text']}"""

    # Создаем варианты ответов
    options = [opt[1] for opt in question['options']]

    await update.message.reply_text(
        question_text,
        parse_mode='Markdown',
        reply_markup=create_quiz_keyboard(options, lang)
    )

    return CHATTING

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа на вопрос теста"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    if not user.get('current_quiz'):
        await query.edit_message_text("❌ Тест не найден!" if lang == 'ru' else "❌ Тест табылган жок!")
        return

    action = query.data.split('_')[2]

    if action == 'finish':
        # Досрочное завершение теста
        await query.edit_message_text("🏁 Тест завершен досрочно!" if lang == 'ru' else "🏁 Тест эрте аяктады!")
        await finish_quiz(update, context)
        return

    # Получаем выбранный ответ
    selected_answer = action  # A, B, C, D

    quiz = user['current_quiz']
    current_idx = quiz['current_question']
    questions = quiz['questions']

    if current_idx >= len(questions):
        return

    question = questions[current_idx]

    # Сохраняем ответ
    quiz['answers'].append({
        'question': current_idx,
        'selected': selected_answer,
        'correct': question.get('correct_answer'),
        'is_correct': selected_answer == question.get('correct_answer'),
        'question_text': question['text'],
        'options': question['options']
    })

    # НЕ показываем правильный ответ сразу
    if lang == 'ru':
        result_text = f"✅ Ответ записан!\n\nПереходим к следующему вопросу..."
    else:
        result_text = f"✅ Жооп жазылды!\n\nКийинки суроого өтөбүз..."

    await query.edit_message_text(result_text, parse_mode='Markdown')

    # Переходим к следующему вопросу
    quiz['current_question'] += 1

    # Ждем 1 секунду перед следующим вопросом
    await asyncio.sleep(1)

    if quiz['current_question'] < len(questions):
        # Показываем следующий вопрос
        next_question = questions[quiz['current_question']]

        if lang == 'ru':
            question_text = f"""🎯 *Тест: Вопрос {quiz['current_question'] + 1} из {len(questions)}*

{next_question['text']}"""
        else:
            question_text = f"""🎯 *Тест: Суроо {quiz['current_question'] + 1} {len(questions)}дан*

{next_question['text']}"""

        options = [opt[1] for opt in next_question['options']]

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=question_text,
            parse_mode='Markdown',
            reply_markup=create_quiz_keyboard(options, lang)
        )
    else:
        # Завершаем тест
        await finish_quiz(update, context)

async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает тест и показывает результаты"""
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    if not user.get('current_quiz'):
        return

    quiz = user['current_quiz']
    answers = quiz['answers']

    # Считаем результаты
    correct_count = sum(1 for a in answers if a.get('is_correct', False))
    total_count = len(answers)
    percentage = (correct_count / total_count * 100) if total_count > 0 else 0

    # Формируем текст результатов
    if lang == 'ru':
        result_text = f"""🎉 *Тест завершен!*

📊 *Результаты:*
✅ Правильных ответов: {correct_count}/{total_count}
📈 Процент выполнения: {percentage:.1f}%
⭐ Оценка: {get_grade(percentage, lang)}

Сейчас я проанализирую твои ошибки и объясню их простыми словами..."""
    else:
        result_text = f"""🎉 *Тест аяктады!*

📊 *Натыйжалар:*
✅ Туура жооптор: {correct_count}/{total_count}
📈 Аткаруу пайызы: {percentage:.1f}%
⭐ Баалоо: {get_grade(percentage, lang)}

Азыр мен каталарыңызды анализдейм жана аларды жөнөкөй сөздөр менен түшүндүрөм..."""

    # Отправляем результаты
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(result_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(result_text, parse_mode='Markdown')

    # Создаем детальный анализ ошибок
    await analyze_mistakes(update, context, quiz, lang)

    # Обновляем прогресс урока
    lesson_id = quiz.get('lesson_id')
    for lesson in user.get('lessons', []):
        if lesson.get('id') == lesson_id:
            lesson['progress'] = int(percentage)
            break

    # Очищаем данные теста
    user['current_quiz'] = None

    # Возвращаем клавиатуру обучения
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Вернуться к обучению:" if lang == 'ru' else "Үйрөнүүгө кайтуу:",
        reply_markup=create_learning_keyboard(lang)
    )

async def analyze_mistakes(update: Update, context: ContextTypes.DEFAULT_TYPE, quiz, lang):
    """Анализирует ошибки и объясняет их"""
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    profile = user.get('profile', {})
    answers = quiz.get('answers', [])

    # Находим неправильные ответы
    wrong_answers = [a for a in answers if not a.get('is_correct', True)]

    if not wrong_answers:
        if lang == 'ru':
            praise = f"""🎊 *Отличный результат!*

Ты ответил правильно на все вопросы! Это показывает, что ты хорошо понял тему.

💡 *Для закрепления знаний:*
1. Попробуй объяснить тему кому-то другому
2. Создай свой тест по этой теме
3. Найди практическое применение знаниям в жизни

Продолжай в том же духе! 💪"""
        else:
            praise = f"""🎊 *Эң жакшы натыйжа!*

Сиз бардык суроолорго туура жооп бердиңиз! Бул сиз теманы жакшы түшүнгөнүңүздү көрсөтөт.

💡 *Билимдерди бекемдөө үчүн:*
1. Теманы башка бирөөгө түшүндүрүүгө аракет кылыңыз
2. Бул тема боюнча өз тестиңизди түзүңүз
3. Билимдерди жашоодо колдонууну табыңыз

Ушуну менен улант! 💪"""

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=praise,
            parse_mode='Markdown'
        )
        return

    # Анализируем каждую ошибку
    if lang == 'ru':
        analysis_text = "🔍 *Анализ ошибок:*\n\n"
    else:
        analysis_text = "🔍 *Каталарды анализдөө:*\n\n"

    for i, wrong in enumerate(wrong_answers[:3]):  # Анализируем до 3 ошибок
        question_text = wrong.get('question_text', '')
        selected = wrong.get('selected', '?')
        correct = wrong.get('correct', '?')

        # Находим тексты вариантов
        options = wrong.get('options', [])
        selected_text = next((opt[1] for opt in options if opt[0] == selected), "Неизвестно")
        correct_text = next((opt[1] for opt in options if opt[0] == correct), "Неизвестно")

        if lang == 'ru':
            analysis_text += f"{i+1}. *Вопрос:* {question_text}\n"
            analysis_text += f"   Твой ответ: {selected}) {selected_text}\n"
            analysis_text += f"   Правильный: {correct}) {correct_text}\n\n"
        else:
            analysis_text += f"{i+1}. *Суроо:* {question_text}\n"
            analysis_text += f"   Сиздин жообуңуз: {selected}) {selected_text}\n"
            analysis_text += f"   Туура жооп: {correct}) {correct_text}\n\n"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=analysis_text,
        parse_mode='Markdown'
    )

    # Создаем промпт для объяснения ошибок
    if lang == 'ru':
        mistake_prompt = f"""Ученик совершил следующие ошибки в тесте:

{analysis_text}

Профиль ученика:
- Возраст: {profile.get('age', 15)} лет
- Интересы: {', '.join(profile.get('interests', []))}
- Стиль обучения: {profile.get('teacherStyle', 'kind_mentor')}

Объясни эти ошибки простыми словами, учитывая возраст и интересы ученика:
1. Почему были допущены эти ошибки?
2. Как правильно понимать эти вопросы?
3. Дай простые аналогии из жизни
4. Предложи способы запомнить правильные ответы
5. Будь поддерживающим и мотивирующим

Используй методы обучения соответствующие возрасту!"""
    else:
        mistake_prompt = f"""Окуучу тестте төмөнкү каталарды жасан:

{analysis_text}

Окуучунун профили:
- Жаш: {profile.get('age', 15)} жаш
- Кызыкчылыктар: {', '.join(profile.get('interests', []))}
- Үйрөнүү стили: {profile.get('teacherStyle', 'kind_mentor')}

Бул каталарды жөнөкөй сөздөр менен түшүндүр, окуучунун жашы менен кызыкчылыктарын эске алганда:
1. Эмне үчүн бул каталар жасан?
2. Бул суроолорду кандай туура түшүнүү керек?
3. Жашоодон жөнөкөй аналогиялар келтир
4. Туура жоопторду эстей билүүнүн жолдорун сунушта
5. Колдоочу жана мотивациялоочу бол

Жашка туура келген үйрөтүү ыкмаларын колдон!"""

    loading_text = "⏳ Анализирую ошибки и готовлю объяснение..." if lang == 'ru' else "⏳ Каталарды анализдейм жана түшүндүрмө даярдап жатам..."
    loading_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=loading_text
    )

    explanation = await call_groq_api(mistake_prompt, profile, lang)

    await loading_msg.edit_text(f"💡 *Объяснение ошибок:*\n\n{explanation}" if lang == 'ru' else f"💡 *Каталардын түшүндүрмөсү:*\n\n{explanation}")

def get_grade(percentage, lang='ru'):
    """Возвращает оценку по проценту"""
    if percentage >= 90:
        return "Отлично! 🌟" if lang == 'ru' else "Эң жакшы! 🌟"
    elif percentage >= 75:
        return "Хорошо! 👍" if lang == 'ru' else "Жакшы! 👍"
    elif percentage >= 60:
        return "Удовлетворительно 👌" if lang == 'ru' else "Канааттанарлык 👌"
    else:
        return "Нужно повторить 📚" if lang == 'ru' else "Кайталоо керек 📚"

async def my_lessons_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    lessons = user.get('lessons', [])

    if not lessons:
        msg = "📭 У тебя пока нет уроков. Создай свой первый урок через меню '➕ Новый урок'!" if lang == 'ru' else "📭 Сизде азырынча сабак жок. Биринчи сабагыңызды '➕ Жаңы сабак' менюсу аркылуу түзүңүз!"
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=create_main_keyboard(lang))
        return

    if lang == 'ru':
        text = "📚 *Твои уроки:*\n\n"
    else:
        text = "📚 *Сиздин сабактарыңыз:*\n\n"

    mode_emoji = {'explanation': '📚', 'practice': '💪', 'quiz': '🎯'}

    for i, lesson in enumerate(lessons[-5:], 1):
        date = lesson['created'][:10]
        progress = lesson.get('progress', 0)

        if lang == 'ru':
            text += f"{i}. *{lesson['topic']}*\n"
            text += f"   {mode_emoji.get(lesson['type'], '📝')}"
            if lesson.get('question_count'):
                text += f" ({lesson['question_count']} вопросов)"
            text += f" | 📅 {date} | 📊 {progress}%\n\n"
        else:
            text += f"{i}. *{lesson['topic']}*\n"
            text += f"   {mode_emoji.get(lesson['type'], '📝')}"
            if lesson.get('question_count'):
                text += f" ({lesson['question_count']} суроо)"
            text += f" | 📅 {date} | 📊 {progress}%\n\n"

    if lang == 'ru':
        text += "\n*Выбери урок для продолжения или создай новый!*"
    else:
        text += "\n*Улантуу үчүн сабакты тандаңыз же жаңысын түзүңүз!*"

    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=create_main_keyboard(lang))

async def handle_chatting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    user_message = update.message.text

    if user_message in ['🏠 Главное меню', '🏠 Меню']:
        await update.message.reply_text(
            "🏠 Возвращаюсь в главное меню..." if lang == 'ru' else "🏠 Негизги менюго кайтам...",
            reply_markup=create_main_keyboard(lang)
        )
        return ConversationHandler.END

    if user_message in ['📊 Прогресс', '📊 Прогресс']:
        lesson = user.get('active_lesson')
        if lesson:
            topic = lesson.get('topic', 'Не указана')
            progress = lesson.get('progress', 0)
            if lang == 'ru':
                text = f"""📊 *Твой прогресс*

📖 *Тема:* {topic}
✅ *Прогресс:* {progress}%
🌟 *Уроков завершено:* {len([l for l in user.get('lessons', []) if l.get('progress', 0) >= 80])}

Продолжай в том же духе! 💪"""
            else:
                text = f"""📊 *Сиздин прогрессиңиз*

📖 *Тема:* {topic}
✅ *Прогресс:* {progress}%
🌟 *Аякталган сабактар:* {len([l for l in user.get('lessons', []) if l.get('progress', 0) >= 80])}

Ушуну менен улант! 💪"""
            await update.message.reply_text(text, parse_mode='Markdown', reply_markup=create_learning_keyboard(lang))
        return CHATTING

    if user_message in ['🔄 Новый вопрос', '🔄 Жаңы суроо']:
        lesson = user.get('active_lesson')
        if lesson:
            topic = lesson.get('topic', 'теме')
            profile = user.get('profile', {})

            if lang == 'ru':
                prompt = f"""Создай новый интересный вопрос по теме "{topic}" для проверки понимания.

Контекст ученика:
- Возраст: {profile.get('age', 15)} лет
- Интересы: {', '.join(profile.get('interests', ['разные темы']))}
- Стиль обучения: {profile.get('teacherStyle', 'kind_mentor')}

Вопрос должен быть:
1. Соответствовать возрасту ученика
2. Связан с интересами ученика
3. Проверять понимание, а не память
4. Иметь наводящие подсказки
5. Быть интересным и увлекательным
6. Использовать проверенные методы обучения

Также дай подсказки и объяснение ответа."""
            else:
                prompt = f""""{topic}" темасы боюнча түшүнүүнү текшерүү үчүн жаңы кызыктуу суроо түз.

Окуучунун контексти:
- Жаш: {profile.get('age', 15)} жаш
- Кызыкчылыктар: {', '.join(profile.get('interests', ['ар кандай темалар']))}
- Үйрөнүү стили: {profile.get('teacherStyle', 'kind_mentor')}

Суроо төмөнкүлөрдү канааттандыруу керек:
1. Окуучунун жашына туура келсин
2. Окуучунун кызыкчылыктары менен байланыштуу болсун
3. Эстеп калууну эмес, түшүнүүнү текшерет
4. Жол көрсөтүүчү көрсөтмөлөрү болсун
5. Кызыктуу жана тартымдуу болсун
6. Текшерилген үйрөтүү ыкмаларын колдонсун

Ошондой эле көрсөтмөлөр жана жооптун түшүндүрмөсүн бер."""

            loading = await update.message.reply_text("⏳ Генерирую интересный вопрос... ✨" if lang == 'ru' else "⏳ Кызыктуу суроо түзүлүүдө... ✨")
            ai_response = await call_groq_api(prompt, profile, lang)
            await loading.edit_text(f"❓ *Новый вопрос по теме \"{topic}\":*\n\n{ai_response}" if lang == 'ru' else f"❓ *\"{topic}\" темасы боюнча жаңы суроо:*\n\n{ai_response}", parse_mode='Markdown')
        else:
            msg = "Сначала создай урок!" if lang == 'ru' else "Алгач сабак түзүңүз!"
            await update.message.reply_text(msg)
        return CHATTING

    if user_message in ['🎯 Начать тест', '🎯 Тестти баштоо']:
        await start_quiz(update, context)
        return CHATTING

    # Обработка обычных вопросов пользователя
    loading = await update.message.reply_text("⏳ Думаю над ответом... 🤔" if lang == 'ru' else "⏳ Жооп жөнүндө ойлонуп жатам... 🤔")

    active_lesson = user.get('active_lesson', {})
    topic = active_lesson.get('topic', 'общая тема')
    profile = user.get('profile', {})

    if lang == 'ru':
        context_prompt = f"""КОНТЕКСТ:
- Текущая тема урока: "{topic}"
- Возраст ученика: {profile.get('age', 15)} лет
- Интересы ученика: {', '.join(profile.get('interests', ['разные темы']))}
- Стиль учителя: {profile.get('teacherStyle', 'kind_mentor')}

ВОПРОС УЧЕНИКА: {user_message}

ОТВЕТЬ на русском языке:
1. Сначала покажи, что понял вопрос
2. Объясни подробно, но понятно для возраста ученика
3. Приведи примеры из интересов ученика
4. Используй проверенные методы обучения
5. Задай уточняющий вопрос чтобы проверить понимание
6. Будь поддерживающим и мотивирующим
7. Используй эмодзи чтобы сделать ответ живым

Помни: цель - не дать ответ, а научить понимать!"""
    else:
        context_prompt = f"""КОНТЕКСТ:
- Учурдагы сабактын темасы: "{topic}"
- Окуучунун жашы: {profile.get('age', 15)} жаш
- Окуучунун кызыкчылыктары: {', '.join(profile.get('interests', ['ар кандай темалар']))}
- Мугалимдин стили: {profile.get('teacherStyle', 'kind_mentor')}

ОКУУЧУНУН СУРООСУ: {user_message}

Кыргыз тилинде ЖООП БЕР:
1. Алгач суроону түшүнгөнүңдү көрсөт
2. Деталдуу, бирок окуучунун жашы үчүн түшүнүктүү түрдө түшүндүр
3. Окуучунун кызыкчылыктарынан мисалдар келтир
4. Текшерилген үйрөтүү ыкмаларын колдон
5. Түшүнүүнү текшерүү үчүн тактоочу суроо бер
6. Колдоочу жана мотивациялоочу бол
7. Жоопту тирүү кылуу үчүн эмодзилерди колдон

Эсиңде болсун: максат - жооп берүү эмес, түшүнүүгө үйрөтүү!"""

    ai_response = await call_groq_api(context_prompt, profile, lang)

    # Обновляем прогресс
    if 'active_lesson' in user and user['active_lesson']:
        current_progress = user['active_lesson'].get('progress', 0)
        if current_progress < 100:
            user['active_lesson']['progress'] = min(100, current_progress + 5)

    await loading.edit_text(f"💡 *Ответ:*\n\n{ai_response}", parse_mode='Markdown')

    if lang == 'ru':
        follow_up = "\n\nЕсть ещё вопросы? Задавай! Или используй кнопки ниже 👇"
    else:
        follow_up = "\n\nДагы суроолор барбы? Сураңыз! Же төмөнкү баскычтарды колдонуңуз 👇"

    await update.message.reply_text(follow_up, reply_markup=create_learning_keyboard(lang))
    return CHATTING

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')
    text = update.message.text

    if text in ['➕ Новый урок', '➕ Жаңы сабак']:
        return await new_lesson_command(update, context)
    elif text in ['📚 Уроки', '📚 Сабактар']:
        return await my_lessons_command(update, context)
    elif text in ['👤 Профиль']:
        return await profile_command(update, context)
    elif text in ['❓ Помощь', '❓ Жардам']:
        return await help_command(update, context)
    else:
        msg = "Выбери действие из меню:" if lang == 'ru' else "Менюдан тандаңыз:"
        await update.message.reply_text(msg, reply_markup=create_main_keyboard(lang))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    lang = user.get('language', 'ru')

    msg = "Действие отменено. Используй меню для продолжения." if lang == 'ru' else "Аракет токтотулду. Улантуу үчүн менюну колдонуңуз."
    await update.message.reply_text(msg, reply_markup=create_main_keyboard(lang))
    return ConversationHandler.END

def main():
    print("🚀 Запускаем бота AiqynLearn с Groq API...")
    print("🔑 Telegram токен:", TELEGRAM_TOKEN[:15] + "...")
    print("🔑 Groq API ключ:", GROQ_API_KEY[:15] + "...")
    print("🤖 Используем модель: llama-3.3-70b-versatile")
    print("🌍 Поддержка языков: Русский и Кыргызский")
    print("🎯 Улучшенные тесты с выбором количества вопросов")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # ConversationHandler для создания профиля
    profile_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANGUAGE: [CallbackQueryHandler(handle_language, pattern='^lang_')],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age)],
            INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interests)],
            TEACHER_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_teacher_style)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # ConversationHandler для создания уроков
    lesson_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(➕ Новый урок|➕ Жаңы сабак)$'), new_lesson_command),
            CommandHandler('newlesson', new_lesson_command)
        ],
        states={
            LESSON_MODE: [CallbackQueryHandler(handle_lesson_mode, pattern='^mode_')],
            QUESTION_COUNT: [CallbackQueryHandler(handle_question_count, pattern='^quiz_count_|quiz_cancel')],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic)],
            CHATTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chatting),
                CallbackQueryHandler(handle_quiz_answer, pattern='^quiz_answer_'),
                CallbackQueryHandler(handle_quiz_answer, pattern='^quiz_finish')
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Добавляем все обработчики
    app.add_handler(profile_conv)
    app.add_handler(lesson_conv)

    # Команды
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('profile', profile_command))
    app.add_handler(CommandHandler('lessons', my_lessons_command))
    app.add_handler(CommandHandler('cancel', cancel))

    # Обработка кнопок главного меню
    app.add_handler(MessageHandler(filters.Regex('^(👤 Профиль|📚 Уроки|📚 Сабактар|❓ Помощь|❓ Жардам)$'), handle_text_messages))

    # Обработка любых других текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    print("✅ Бот настроен и запущен!")
    print("💬 Отправь /start в Telegram своему боту!")
    print("⏹️ Нажми Ctrl+C для остановки")
    print("-" * 50)

    # Запускаем polling
    app.run_polling(
        poll_interval=1.0,
        timeout=10,
        bootstrap_retries=3,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска: {e}")
