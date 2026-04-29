import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ============= КОНФИГ =============
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '8310237815:AAGymIIWTuSgwvEpnvx22a3ND67nH7X90kg')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8346538289'))
GROUP_ID = int(os.getenv('GROUP_ID', '-5096890693'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///metro_shop.db')

# ============= ЛОГИРОВАНИЕ =============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============= БД =============
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    service_type = Column(String(255), nullable=False)
    card_number = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)
    percentage = Column(Integer, nullable=False)
    admin_id = Column(Integer, nullable=False)
    participants = Column(JSON, default=None)
    created_at = Column(DateTime, default=datetime.now)
    status = Column(String(20), default='active')

def init_db():
    """Инициализация БД"""
    Base.metadata.create_all(engine)

def add_order(service_type, card_number, amount, percentage, admin_id):
    """Добавить новый заказ"""
    session = Session()
    order = Order(
        service_type=service_type,
        card_number=card_number,
        amount=amount,
        percentage=percentage,
        admin_id=admin_id,
        participants=[]
    )
    session.add(order)
    session.commit()
    order_id = order.id
    session.close()
    return order_id

def get_order(order_id):
    """Получить заказ по ID"""
    session = Session()
    order = session.query(Order).filter(Order.id == order_id).first()
    session.close()
    
    if order:
        return {
            'id': order.id,
            'service_type': order.service_type,
            'card_number': order.card_number,
            'amount': order.amount,
            'percentage': order.percentage,
            'admin_id': order.admin_id,
            'participants': order.participants or [],
            'status': order.status,
            'created_at': order.created_at
        }
    return None

def update_order_participants(order_id, participants):
    """Обновить участников заказа"""
    session = Session()
    order = session.query(Order).filter(Order.id == order_id).first()
    if order:
        order.participants = participants
        session.commit()
    session.close()

def get_all_orders():
    """Получить все заказы"""
    session = Session()
    orders = session.query(Order).all()
    session.close()
    return orders

def update_order_status(order_id, status):
    """Обновить статус заказа"""
    session = Session()
    order = session.query(Order).filter(Order.id == order_id).first()
    if order:
        order.status = status
        session.commit()
    session.close()

# ============= STATES =============
SERVICE_TYPE, CARD_NUMBER, AMOUNT, PERCENTAGE = range(4)

# ============= ФУНКЦИИ БОТА =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    keyboard = []
    
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📝 Создать заказ", callback_data='create_order')],
            [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
            [InlineKeyboardButton("📋 Список заказов", callback_data='list_orders')],
        ]
        text = "🎮 **Metro Shop PUBG Mobile Bot**\n\n⚙️ Режим администратора"
    else:
        keyboard = [
            [InlineKeyboardButton("ℹ️ О боте", callback_data='about')],
        ]
        text = "🎮 **Metro Shop PUBG Mobile Bot**\n\nДобро пожаловать!"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопок"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    # Проверка прав администратора
    if user_id != ADMIN_ID and query.data in ['create_order', 'stats', 'list_orders']:
        await query.answer("❌ Недостаточно прав!", show_alert=True)
        return
    
    if query.data == 'create_order':
        await query.edit_message_text(
            "📝 Введите тип услуги (например: Сопровождение, Фарм, Скупка рангов):"
        )
        return SERVICE_TYPE
    
    elif query.data == 'stats':
        orders = get_all_orders()
        total_orders = len(orders)
        active_orders = len([o for o in orders if o.status == 'active'])
        completed_orders = len([o for o in orders if o.status == 'completed'])
        
        total_sum = sum(o.amount for o in orders)
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        stats_text = (
            f"📊 **СТАТИСТИКА**\n\n"
            f"📈 Всего заказов: {total_orders}\n"
            f"✅ Активных: {active_orders}\n"
            f"✔️ Завершено: {completed_orders}\n"
            f"💰 Общая сумма: {total_sum}кк\n"
            f"📅 Дата последнего обновления: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        await query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == 'list_orders':
        orders = get_all_orders()
        
        if not orders:
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📋 Заказов не найдено",
                reply_markup=reply_markup
            )
            return
        
        orders_text = "📋 **СПИСОК АКТИВНЫХ ЗАКАЗОВ**\n\n"
        
        for order in orders:
            if order.status == 'active':
                participants_count = len(order.participants) if order.participants else 0
                orders_text += (
                    f"ID: `{order.id}` | {order.service_type}\n"
                    f"Карта: {order.card_number} | Сумма: {order.amount}кк\n"
                    f"Участников: {participants_count}/3\n"
                    f"Статус: ✅ Активен\n\n"
                )
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            orders_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == 'about':
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        about_text = (
            "ℹ️ **О боте**\n\n"
            "🎮 Metro Shop PUBG Mobile Bot\n"
            "Система управления заказами для проведения услуг\n\n"
            "✨ Возможности:\n"
            "• Просмотр активных заказов\n"
            "• Присоединение к заказам\n"
            "• Автоматическое распределение процентов\n\n"
            "👥 Максимум участников: 3\n"
            "💰 Автоматическое разделение заработка"
        )
        
        await query.edit_message_text(
            about_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == 'back_to_menu':
        await start(update, context)

async def handle_service_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка типа услуги"""
    context.user_data['service_type'] = update.message.text
    await update.message.reply_text(
        "🏦 Введите номер карты (например: 8карта, 2карта):",
        parse_mode='Markdown'
    )
    return CARD_NUMBER

async def handle_card_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка номера карты"""
    context.user_data['card_number'] = update.message.text
    await update.message.reply_text(
        "💰 Введите сумму заказа в кк (например: 25):",
        parse_mode='Markdown'
    )
    return AMOUNT

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы"""
    try:
        amount = int(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0")
            return AMOUNT
        
        context.user_data['amount'] = amount
        await update.message.reply_text(
            "📊 Введите процент разделения между участниками (0-100):",
            parse_mode='Markdown'
        )
        return PERCENTAGE
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите числовое значение")
        return AMOUNT

async def handle_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка процента и отправка в группу"""
    try:
        percentage = int(update.message.text)
        if not (0 <= percentage <= 100):
            await update.message.reply_text("❌ Процент должен быть от 0 до 100")
            return PERCENTAGE
        
        context.user_data['percentage'] = percentage
        
        # Сохраняем в БД
        order_id = add_order(
            service_type=context.user_data['service_type'],
            card_number=context.user_data['card_number'],
            amount=context.user_data['amount'],
            percentage=percentage,
            admin_id=update.effective_user.id
        )
        
        # Подготавливаем данные
        service = context.user_data['service_type']
        card = context.user_data['card_number']
        amount = context.user_data['amount']
        
        # Клавиатура для группы
        keyboard = [
            [InlineKeyboardButton(f"✅ Участвую (0/3)", callback_data=f'join_{order_id}')],
            [InlineKeyboardButton(f"❌ Отказ", callback_data=f'decline_{order_id}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Сообщение в группу
        message_text = (
            f"🎯 **НОВЫЙ ЗАКАЗ**\n\n"
            f"📌 Услуга: `{service}`\n"
            f"🏦 Карта: `{card}`\n"
            f"💰 Сумма: `{amount}` кк\n"
            f"📊 Процент дохода: `{percentage}%`\n"
            f"👥 Участников: `0/3`\n\n"
            f"🔑 ID заказа: `{order_id}`\n\n"
            f"_Нажмите кнопку ниже чтобы участвовать_"
        )
        
        await context.bot.send_message(
            chat_id=GROUP_ID,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            f"✅ **Заказ создан успешно!**\n\n"
            f"ID: `{order_id}`\n"
            f"Уведомление отправлено в группу",
            parse_mode='Markdown'
        )
        
        # Очищаем данные
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите числовое значение")
        return PERCENTAGE

async def join_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Присоединиться к заказу"""
    query = update.callback_query
    
    order_id = int(query.data.split('_')[1])
    user_id = query.from_user.id
    user_name = query.from_user.first_name or query.from_user.username or f"User{user_id}"
    
    order = get_order(order_id)
    if not order:
        await query.answer("❌ Заказ не найден!", show_alert=True)
        return
    
    if order['status'] != 'active':
        await query.answer("❌ Заказ уже завершен!", show_alert=True)
        return
    
    participants = order['participants'] or []
    
    # Проверяем, участвует ли уже
    if any(p['user_id'] == user_id for p in participants):
        await query.answer("⚠️ Вы уже участвуете в этом заказе!", show_alert=True)
        return
    
    # Проверяем максимум участников
    if len(participants) >= 3:
        await query.answer("❌ Максимум 3 участника! Мест больше нет", show_alert=True)
        return
    
    # Вычисляем процент на человека
    percent_per_person = order['percentage'] // 3
    remainder = order['percentage'] % 3
    
    # Добавляем остаток первому участнику
    if len(participants) == 0:
        percent_per_person += remainder
    
    # Добавляем участника
    participants.append({
        'user_id': user_id,
        'username': user_name,
        'percentage_per_person': percent_per_person
    })
    
    update_order_participants(order_id, participants)
    
    # Обновляем сообщение в группе
    keyboard = [
        [InlineKeyboardButton(f"✅ Участвую ({len(participants)}/3)", callback_data=f'join_{order_id}')],
        [InlineKeyboardButton(f"❌ Отказ", callback_data=f'decline_{order_id}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Список участников
    participant_list = ""
    for i, p in enumerate(participants, 1):
        participant_list += f"{i}. 👤 {p['username']} — {p['percentage_per_person']}%\n"
    
    message_text = (
        f"🎯 **НОВЫЙ ЗАКАЗ**\n\n"
        f"📌 Услуга: `{order['service_type']}`\n"
        f"🏦 Карта: `{order['card_number']}`\n"
        f"💰 Сумма: `{order['amount']}` кк\n"
        f"📊 Процент дохода: `{order['percentage']}%`\n"
        f"👥 Участников: `{len(participants)}/3`\n\n"
        f"**Участники заказа:**\n{participant_list}\n"
        f"🔑 ID заказа: `{order_id}`"
    )
    
    try:
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except:
        pass
    
    await query.answer(
        f"✅ Добро пожаловать!\n{order['percentage'] // 3}% вашего дохода",
        show_alert=True
    )

async def decline_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отказаться от заказа"""
    query = update.callback_query
    await query.answer("❌ Вы отказались от заказа", show_alert=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "❓ **СПРАВКА**\n\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n\n"
        "**Администратору:**\n"
        "📝 Создать заказ - новый заказ\n"
        "📊 Статистика - информация\n"
        "📋 Список заказов - все заказы\n"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Запуск бота"""
    init_db()
    
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN':
        logger.error("❌ BOT_TOKEN не установлен!")
        return
    
    if ADMIN_ID == 0:
        logger.error("❌ ADMIN_ID не установлен!")
        return
    
    if GROUP_ID == 0:
        logger.error("❌ GROUP_ID не установлен!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для создания заказа
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern='^create_order$')],
        states={
            SERVICE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_service_type)],
            CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card_number)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            PERCENTAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_percentage)],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    
    # Обработчики
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CallbackQueryHandler(join_order, pattern='^join_'))
    app.add_handler(CallbackQueryHandler(decline_order, pattern='^decline_'))
    
    logger.info("✅ Бот запущен и готов к работе!")
    app.run_polling()

if __name__ == '__main__':
    main()
