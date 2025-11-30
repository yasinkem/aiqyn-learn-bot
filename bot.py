import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from groq import Groq
from dotenv import load_dotenv
from prompts import create_teacher_prompt

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Groq API
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# Состояния для ConversationHandler
AGE, SUBJECT, INTERESTS, TEACHER_STYLE, LEARNING = range(5)

# Данные пользователя (в памяти)
user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы с ботом"""
    user_id = update.effective_user.id
    user_data[user_id] = {}
    
    await update.message.reply_text(
        "🌟 Привет! Я AIQYN — твой персональный ИИ-учитель!\n\n"
        "Я не просто дам тебе ответ, а научу ПОНИМАТЬ. "
        "Объясню через то, что тебе интересно, и помогу по-настоящему разобраться.\n\n"
        "Давай познакомимся! Сколько тебе лет? (напиши число)"
    )
    return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем возраст"""
    user_id = update.effective_user.id
    try:
        age = int(update.message.text)
        if age < 6 or age > 100:
            await update.message.reply_text("Введи корректный возраст (от 6 до 100 лет)")
            return AGE
        
        user_data[user_id]['age'] = age
        
        # Определяем класс по возрасту
        if age <= 10:
            user_data[user_id]['level'] = "начальная школа"
        elif age <= 15:
            user_data[user_id]['level'] = "средняя школа"
        elif age <= 18:
            user_data[user_id]['level'] = "старшая школа"
        else:
            user_data[user_id]['level'] = "взрослый"
        
        # Клавиатура для выбора предмета
        keyboard = [
            ['Математика', 'Физика'],
            ['Химия', 'Биология'],
            ['История', 'Программирование']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        
        await update.message.reply_text(
            f"Отлично! Тебе {age} лет.\n\n"
            "Какой предмет тебя интересует?",
            reply_markup=reply_markup
        )
        return SUBJECT
        
    except ValueError:
        await update.message.reply_text("Напиши своё возраст числом, например: 15")
        return AGE


async def get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем предмет"""
    user_id = update.effective_user.id
    user_data[user_id]['subject'] = update.message.text
    
    keyboard = [
        ['⚽ Спорт', '🎮 Игры'],
        ['🎬 Фильмы/Аниме', '🚗 Машины'],
        ['💻 Технологии', '🎨 Искусство'],
        ['🎵 Музыка', '📚 Книги']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Супер! Теперь выбери, что тебе интересно.\n\n"
        "Я буду объяснять через примеры из того, что ты любишь!",
        reply_markup=reply_markup
    )
    return INTERESTS


async def get_interests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем интересы"""
    user_id = update.effective_user.id
    user_data[user_id]['interests'] = update.message.text
    
    keyboard = [
        ['😊 Добрый наставник', '💪 Строгий тренер'],
        ['😎 Мемный друг', '🥋 Мудрый сенсей'],
        ['🔥 Мотивационный коуч']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    
    await update.message.reply_text(
        "Отлично! Последний вопрос:\n\n"
        "Какой стиль учителя тебе больше подходит?",
        reply_markup=reply_markup
    )
    return TEACHER_STYLE


async def get_teacher_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем стиль учителя и переходим к обучению"""
    user_id = update.effective_user.id
    user_data[user_id]['teacher_style'] = update.message.text
    user_data[user_id]['conversation_history'] = []
    
    await update.message.reply_text(
        "🎉 Всё готово! Теперь я твой персональный учитель.\n\n"
        "Задай мне любой вопрос по теме, которую хочешь понять!\n\n"
        "Например:\n"
        "• Объясни второй закон Ньютона\n"
        "• Что такое фотосинтез?\n"
        "• Как решать квадратные уравнения?\n\n"
        "💡 Помни: я не дам готовый ответ, а помогу ПОНЯТЬ!",
        reply_markup=ReplyKeyboardRemove()
    )
    return LEARNING


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка вопросов через Groq API"""
    user_id = update.effective_user.id
    user_question = update.message.text
    
    if user_id not in user_data:
        await update.message.reply_text(
            "Давай сначала познакомимся! Нажми /start"
        )
        return LEARNING
    
    # Показываем что бот думает
    await update.message.reply_chat_action("typing")
    
    try:
        # Получаем данные пользователя
        profile = user_data[user_id]
        
        # Создаём промпт
        system_prompt = create_teacher_prompt(profile)
        
        # Добавляем вопрос в историю
        profile['conversation_history'].append({
            "role": "user",
            "content": user_question
        })
        
        # Формируем сообщения для Groq (нужно добавить system в первое сообщение)
        messages = [{"role": "system", "content": system_prompt}] + profile['conversation_history']
        
        # Вызываем Groq API
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Быстрая и качественная модель
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
            top_p=1,
            stream=False
        )
        
        # Получаем ответ
        assistant_message = response.choices[0].message.content
        
        # Добавляем ответ в историю
        profile['conversation_history'].append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Ограничиваем историю (последние 10 сообщений)
        if len(profile['conversation_history']) > 10:
            profile['conversation_history'] = profile['conversation_history'][-10:]
        
        # Отправляем ответ
        await update.message.reply_text(assistant_message)
        
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        await update.message.reply_text(
            "Упс! Произошла ошибка. Попробуй ещё раз или напиши /start чтобы начать заново."
        )
    
    return LEARNING


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс настроек"""
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await update.message.reply_text(
        "Настройки сброшены! Нажми /start чтобы начать заново."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена"""
    await update.message.reply_text(
        "До встречи! Нажми /start когда захочешь учиться снова.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    """Запуск бота"""
    # Создаём приложение
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            INTERESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_interests)],
            TEACHER_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_teacher_style)],
            LEARNING: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('reset', reset),
            CommandHandler('start', start)
        ],
    )
    
    app.add_handler(conv_handler)
    
    # Запускаем бота
    logger.info("🤖 AIQYN Bot запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
