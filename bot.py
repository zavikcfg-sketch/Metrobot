import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from collections import defaultdict
import json

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
    status = Column(String(20), default='active')  # active, completed, cancelled
    message_id = Column(Integer, nullable=True)
    message_chat_id = Column(Integer, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    is_locked = Column(Boolean, default=False)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    total_orders = Column(Integer, default=0)
    completed_orders = Column(Integer, default=0)
    total_earned = Column(Float, default=0)
    rating = Column(Float, default=5.0)
    ban_status = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)

class Complaint(Base):
    __tablename__ = 'complaints'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, nullable=False)
    complainer_id = Column(Integer, nullable=False)
    defendant_id = Column(Integer, nullable=False)
    reason = Column(String(500), nullable=False)
    evidence = Column(String(500))
    status = Column(String(20), default='pending')  # pending, resolved, rejected
    created_at = Column(DateTime, default=datetime.now)

class Referral(Base):
    __tablename__ = 'referrals'
    
    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, nullable=False)
    referred_id = Column(Integer, nullable=False)
    bonus = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now)

def init_db():
    """Инициализация БД"""
    Base.metadata.create_all(engine)

# ============= ФУНКЦИИ БД ЗАКАЗОВ =============

def add_order(service_type, card_number, amount, percentage, admin_id):
    """Добавить новый заказ"""
    session = Session()
    try:
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
        return order.id
    finally:
        session.close()

def get_order(order_id):
    """Получить заказ по ID"""
    session = Session()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
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
                'created_at': order.created_at,
                'message_id': order.message_id,
                'message_chat_id': order.message_chat_id,
                'completed_at': order.completed_at,
                'is_locked': order.is_locked
            }
        return None
    finally:
        session.close()

def update_order_participants(order_id, participants):
    """Обновить участников заказа"""
    session = Session()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        if order:
            order.participants = participants
            session.commit()
    finally:
        session.close()

def update_order_message_info(order_id, message_id, chat_id):
    """Обновить информацию о сообщении"""
    session = Session()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        if order:
            order.message_id = message_id
            order.message_chat_id = chat_id
            session.commit()
    finally:
        session.close()

def get_all_orders():
    """Получить все заказы"""
    session = Session()
    try:
        return session.query(Order).all()
    finally:
        session.close()

def update_order_status(order_id, status):
    """Обновить статус заказа"""
    session = Session()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        if order:
            order.status = status
            if status == 'completed':
                order.completed_at = datetime.now()
            session.commit()
    finally:
        session.close()

def lock_order(order_id):
    """Заблокировать заказ"""
    session = Session()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        if order:
            order.is_locked = True
            session.commit()
    finally:
        session.close()

# ============= ФУНКЦИИ БД ПОЛЬЗОВАТЕЛЕЙ =============

def get_or_create_user(user_id, username, first_name):
    """Получить или создать пользователя"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(
                user_id=user_id,
                username=username,
                first_name=first_name
            )
            session.add(user)
            session.commit()
        else:
            user.last_activity = datetime.now()
            session.commit()
        return user
    finally:
        session.close()

def get_user_stats(user_id):
    """Получить статистику пользователя"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            return {
                'total_orders': user.total_orders,
                'completed_orders': user.completed_orders,
                'total_earned': user.total_earned,
                'rating': user.rating,
                'ban_status': user.ban_status,
                'created_at': user.created_at
            }
        return None
    finally:
        session.close()

def update_user_earnings(user_id, amount):
    """Обновить заработки пользователя"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.total_earned += amount
            user.completed_orders += 1
            session.commit()
    finally:
        session.close()

def ban_user(user_id):
    """Забанить пользователя"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.ban_status = True
            session.commit()
    finally:
        session.close()

def unban_user(user_id):
    """Разбанить пользователя"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.ban_status = False
            session.commit()
    finally:
        session.close()

def update_user_rating(user_id, rating):
    """Обновить рейтинг пользователя"""
    session = Session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.rating = max(1.0, min(5.0, rating))
            session.commit()
    finally:
        session.close()

# ============= ФУНКЦИИ ЖАЛОБ =============

def create_complaint(order_id, complainer_id, defendant_id, reason, evidence=None):
    """Создать жалобу"""
    session = Session()
    try:
        complaint = Complaint(
            order_id=order_id,
            complainer_id=complainer_id,
            defendant_id=defendant_id,
            reason=reason,
            evidence=evidence
        )
        session.add(complaint)
        session.commit()
        return complaint.id
    finally:
        session.close()

def get_pending_complaints():
    """Получить все ожидающие жалобы"""
    session = Session()
    try:
        return session.query(Complaint).filter(Complaint.status == 'pending').all()
    finally:
        session.close()

def resolve_complaint(complaint_id, resolution):
    """Разрешить жалобу"""
    session = Session()
    try:
        complaint = session.query(Complaint).filter(Complaint.id == complaint_id).first()
        if complaint:
            complaint.status = 'resolved'
            session.commit()
    finally:
        session.close()

# ============= ФУНКЦИИ РЕФЕРАЛЬНОЙ ПРОГРАММЫ =============

def create_referral(referrer_id, referred_id, bonus=50):
    """Создать реферальную связь"""
    session = Session()
    try:
        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            bonus=bonus
        )
        session.add(referral)
        session.commit()
        return referral.id
    finally:
        session.close()

def get_referrals(user_id):
    """Получить рефералов пользователя"""
    session = Session()
    try:
        return session.query(Referral).filter(Referral.referrer_id == user_id).all()
    finally:
        session.close()

# ============= STATES =============
SERVICE_TYPE, CARD_NUMBER, AMOUNT, PERCENTAGE = range(4)
COMPLAINT_REASON, COMPLAINT_EVIDENCE = range(2)
PROMO_NAME, PROMO_CODE, PROMO_DISCOUNT = range(3)

# ============= ФУНКЦИИ БОТА =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "NoUsername"
    first_name = update.effective_user.first_name or "User"
    
    # Создаем или обновляем пользователя
    get_or_create_user(user_id, username, first_name)
    
    keyboard = []
    
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📝 Создать заказ", callback_data='create_order')],
            [InlineKeyboardButton("📊 Статистика", callback_data='stats')],
            [InlineKeyboardButton("📋 Все заказы", callback_data='list_orders')],
            [InlineKeyboardButton("👥 Управление юзерами", callback_data='manage_users')],
            [InlineKeyboardButton("⚖️ Жалобы", callback_data='complaints')],
            [InlineKeyboardButton("🎁 Промо коды", callback_data='promo_codes')],
        ]
        text = "🎮 **Metro Shop PUBG Mobile Bot**\n\n⚙️ **АДМИНИСТРАТОР**"
    else:
        keyboard = [
            [InlineKeyboardButton("📋 Активные заказы", callback_data='my_orders')],
            [InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile')],
            [InlineKeyboardButton("🎁 Рефералы", callback_data='my_referrals')],
            [InlineKeyboardButton("⭐ Топ игроков", callback_data='top_players')],
            [InlineKeyboardButton("ℹ️ О боте", callback_data='about')],
        ]
        text = "🎮 **Metro Shop PUBG Mobile Bot**\n\n👋 Добро пожаловать!"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        try:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            pass

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопок"""
    query = update.callback_query
    user_id = query.from_user.id
    
    try:
        await query.answer()
    except:
        pass
    
    # ============= АДМИН ФУНКЦИИ =============
    
    if user_id == ADMIN_ID:
        
        if query.data == 'create_order':
            try:
                await query.edit_message_text(
                    "📝 Введите тип услуги (Сопровождение, Фарм, Скупка рангов и т.д.):"
                )
            except:
                pass
            return SERVICE_TYPE
        
        elif query.data == 'stats':
            orders = get_all_orders()
            users = Session().query(User).all()
            
            total_orders = len(orders)
            active_orders = len([o for o in orders if o.status == 'active'])
            completed_orders = len([o for o in orders if o.status == 'completed'])
            total_sum = sum(o.amount for o in orders)
            total_users = len(users)
            
            avg_order_value = total_sum // total_orders if total_orders > 0 else 0
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            stats_text = (
                f"📊 **ОБЩАЯ СТАТИСТИКА**\n\n"
                f"📈 Заказы:\n"
                f"  • Всего: {total_orders}\n"
                f"  • Активных: {active_orders}\n"
                f"  • Завершено: {completed_orders}\n\n"
                f"💰 Финансы:\n"
                f"  • Общая сумма: {total_sum}кк\n"
                f"  • Средний заказ: {avg_order_value}кк\n\n"
                f"👥 Пользователи:\n"
                f"  • Всего: {total_users}\n\n"
                f"📅 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            try:
                await query.edit_message_text(
                    stats_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'list_orders':
            orders = get_all_orders()
            
            if not orders:
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.edit_message_text(
                        "📋 Заказов не найдено",
                        reply_markup=reply_markup
                    )
                except:
                    pass
                return
            
            # Разделяем по статусам
            active = [o for o in orders if o.status == 'active']
            completed = [o for o in orders if o.status == 'completed']
            
            orders_text = f"📋 **СПИСОК ЗАКАЗОВ**\n\n"
            
            if active:
                orders_text += "✅ **АКТИВНЫЕ:**\n"
                for order in active[-5:]:  # Последние 5
                    participants_count = len(order.participants) if order.participants else 0
                    orders_text += (
                        f"ID: `{order.id}` | {order.service_type}\n"
                        f"💰 {order.amount}кк | 👥 {participants_count}/3\n"
                        f"⏱️ {order.created_at.strftime('%d.%m %H:%M')}\n\n"
                    )
            
            if completed:
                orders_text += "✔️ **ЗАВЕРШЕННЫЕ** (последние 3):\n"
                for order in completed[-3:]:
                    orders_text += (
                        f"ID: `{order.id}` | {order.service_type}\n"
                        f"💰 {order.amount}кк\n"
                        f"✅ {order.completed_at.strftime('%d.%m %H:%M')}\n\n"
                    )
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    orders_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'manage_users':
            users = Session().query(User).all()
            
            total = len(users)
            banned = len([u for u in users if u.ban_status])
            
            keyboard = [
                [InlineKeyboardButton("🔍 Поиск юзера", callback_data='search_user')],
                [InlineKeyboardButton("🚫 Забаненные", callback_data='banned_users')],
                [InlineKeyboardButton("⭐ Топ рейтинг", callback_data='top_rating')],
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            users_text = (
                f"👥 **УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ**\n\n"
                f"Всего: {total}\n"
                f"Забаненно: {banned}\n"
                f"Активных: {total - banned}"
            )
            
            try:
                await query.edit_message_text(
                    users_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'complaints':
            complaints = get_pending_complaints()
            
            if not complaints:
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.edit_message_text(
                        "⚖️ Нет активных жалоб",
                        reply_markup=reply_markup
                    )
                except:
                    pass
                return
            
            complaints_text = "⚖️ **АКТИВНЫЕ ЖАЛОБЫ**\n\n"
            
            for complaint in complaints:
                complaints_text += (
                    f"ID: `{complaint.id}` | Заказ: `{complaint.order_id}`\n"
                    f"📝 {complaint.reason}\n"
                    f"⏱️ {complaint.created_at.strftime('%d.%m %H:%M')}\n\n"
                )
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    complaints_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'promo_codes':
            keyboard = [
                [InlineKeyboardButton("➕ Создать промо", callback_data='create_promo')],
                [InlineKeyboardButton("📋 Список промо", callback_data='list_promos')],
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    "🎁 **ПРОМО КОДЫ**",
                    reply_markup=reply_markup
                )
            except:
                pass
    
    # ============= ПОЛЬЗОВАТЕЛЬСКИЕ ФУНКЦИИ =============
    
    else:
        if query.data == 'my_orders':
            orders = get_all_orders()
            user_orders = []
            
            for order in orders:
                if order.participants:
                    for p in order.participants:
                        if p['user_id'] == user_id:
                            user_orders.append(order)
                            break
            
            if not user_orders:
                keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await query.edit_message_text(
                        "📋 У вас пока нет заказов",
                        reply_markup=reply_markup
                    )
                except:
                    pass
                return
            
            orders_text = "📋 **МОИ ЗАКАЗЫ**\n\n"
            
            for order in user_orders[-10:]:
                orders_text += (
                    f"ID: `{order.id}` | {order.service_type}\n"
                    f"💰 {order.amount}кк | 📊 {order.percentage}%\n"
                    f"🏦 {order.card_number}\n"
                    f"Статус: {'✅ Активен' if order.status == 'active' else '✔️ Завершен'}\n\n"
                )
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    orders_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'my_profile':
            stats = get_user_stats(user_id)
            username = update.effective_user.username or "NoUsername"
            
            profile_text = (
                f"👤 **ПРОФИЛЬ** @{username}\n\n"
                f"📊 Статистика:\n"
                f"  • Всего заказов: {stats['total_orders']}\n"
                f"  • Завершено: {stats['completed_orders']}\n"
                f"  • Заработано: {stats['total_earned']:.0f}%\n"
                f"  • Рейтинг: {'⭐' * int(stats['rating'])} ({stats['rating']:.1f}/5.0)\n\n"
                f"📅 Дата регистрации: {stats['created_at'].strftime('%d.%m.%Y')}"
            )
            
            keyboard = [
                [InlineKeyboardButton("🎁 Реферальная ссылка", callback_data='gen_referral')],
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    profile_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'my_referrals':
            referrals = get_referrals(user_id)
            
            ref_text = f"🎁 **РЕФЕРАЛЫ** ({len(referrals)})\n\n"
            
            if referrals:
                total_bonus = sum(r.bonus for r in referrals)
                ref_text += f"Получено бонусов: {total_bonus}%\n\n"
                
                for ref in referrals:
                    ref_text += f"👤 User{ref.referred_id}\n• Бонус: +{ref.bonus}%\n\n"
            else:
                ref_text += "Рефералов еще нет\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🔗 Получить ссылку", callback_data='gen_referral')],
                [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    ref_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'top_players':
            users = Session().query(User).order_by(User.rating.desc()).limit(10).all()
            
            top_text = "⭐ **ТОП 10 ИГРОКОВ**\n\n"
            
            for i, user in enumerate(users, 1):
                stars = '⭐' * int(user.rating)
                top_text += (
                    f"{i}. @{user.username} ({user.rating:.1f}★)\n"
                    f"   💰 Заказов: {user.completed_orders}\n\n"
                )
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    top_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'about':
            about_text = (
                "ℹ️ **О БОТЕ**\n\n"
                "🎮 Metro Shop PUBG Mobile Bot v2.0\n\n"
                "✨ **Возможности:**\n"
                "• 📝 Управление заказами\n"
                "• 👥 Коллаборация игроков\n"
                "• 💰 Распределение процентов\n"
                "• ⭐ Система рейтинга\n"
                "• 🎁 Реферальная программа\n"
                "• ⚖️ Система жалоб\n"
                "• 🎁 Промо коды\n\n"
                "👥 Максимум участников: 3\n"
                "💬 Техподдержка: @admin"
            )
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    about_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        elif query.data == 'gen_referral':
            referral_code = f"ref_{user_id}_{datetime.now().timestamp()}"
            referral_link = f"https://t.me/MetroShopBot?start={referral_code}"
            
            ref_text = (
                f"🔗 **ВАША РЕФЕРАЛЬНАЯ ССЫЛКА**\n\n"
                f"`{referral_link}`\n\n"
                f"Получайте +50% от дохода каждого приглашенного игрока!\n"
                f"Максимум рефералов: без ограничений"
            )
            
            keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    ref_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            except:
                pass
    
    if query.data == 'back_to_menu':
        await start(update, context)

async def handle_service_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка типа услуги"""
    if not update.message:
        return SERVICE_TYPE
    
    context.user_data['service_type'] = update.message.text
    await update.message.reply_text(
        "🏦 Введите номер карты (8карта, 2карта и т.д.):"
    )
    return CARD_NUMBER

async def handle_card_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка номера карты"""
    if not update.message:
        return CARD_NUMBER
    
    context.user_data['card_number'] = update.message.text
    await update.message.reply_text(
        "💰 Введите сумму в кк (например: 25):"
    )
    return AMOUNT

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка суммы"""
    if not update.message:
        return AMOUNT
    
    try:
        amount = int(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть больше 0")
            return AMOUNT
        
        context.user_data['amount'] = amount
        await update.message.reply_text(
            "📊 Введите процент (0-100):"
        )
        return PERCENTAGE
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return AMOUNT

async def handle_percentage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка процента и отправка в группу"""
    if not update.message:
        return PERCENTAGE
    
    try:
        percentage = int(update.message.text)
        if not (0 <= percentage <= 100):
            await update.message.reply_text("❌ Процент: 0-100")
            return PERCENTAGE
        
        context.user_data['percentage'] = percentage
        
        # Создаем заказ
        order_id = add_order(
            service_type=context.user_data['service_type'],
            card_number=context.user_data['card_number'],
            amount=context.user_data['amount'],
            percentage=percentage,
            admin_id=update.effective_user.id
        )
        
        # Готовим сообщение
        service = context.user_data['service_type']
        card = context.user_data['card_number']
        amount = context.user_data['amount']
        
        keyboard = [
            [InlineKeyboardButton(f"✅ Участвую (0/3)", callback_data=f'join_{order_id}')],
            [InlineKeyboardButton(f"❌ Отказ", callback_data=f'decline_{order_id}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            f"🎯 **НОВЫЙ ЗАКАЗ**\n\n"
            f"📌 Услуга: `{service}`\n"
            f"🏦 Карта: `{card}`\n"
            f"💰 Сумма: `{amount}` кк\n"
            f"📊 Доход: `{percentage}%`\n"
            f"👥 Участников: `0/3`\n\n"
            f"🔑 ID: `{order_id}`"
        )
        
        try:
            msg = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            update_order_message_info(order_id, msg.message_id, GROUP_ID)
            
            await update.message.reply_text(
                f"✅ Заказ создан!\n\n"
                f"ID: `{order_id}`",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            await update.message.reply_text(
                f"⚠️ Заказ создан (ID: {order_id}), но ошибка при отправке в группу"
            )
        
        context.user_data.clear()
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Введите число")
        return PERCENTAGE

async def join_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Присоединиться к заказу"""
    query = update.callback_query
    
    try:
        await query.answer()
    except:
        pass
    
    order_id = int(query.data.split('_')[1])
    user_id = query.from_user.id
    user_name = query.from_user.first_name or query.from_user.username or f"User{user_id}"
    
    # Проверка бана
    stats = get_user_stats(user_id)
    if stats and stats['ban_status']:
        try:
            await query.answer("🚫 Вы забаненны!", show_alert=True)
        except:
            pass
        return
    
    order = get_order(order_id)
    if not order:
        try:
            await query.answer("❌ Заказ не найден!", show_alert=True)
        except:
            pass
        return
    
    if order['status'] != 'active':
        try:
            await query.answer("❌ Заказ завершен!", show_alert=True)
        except:
            pass
        return
    
    if order['is_locked']:
        try:
            await query.answer("🔒 Заказ заблокирован!", show_alert=True)
        except:
            pass
        return
    
    participants = order['participants'] or []
    
    # Проверяем, участвует ли уже
    if any(p['user_id'] == user_id for p in participants):
        try:
            await query.answer("⚠️ Вы уже участвуете!", show_alert=True)
        except:
            pass
        return
    
    # Максимум участников
    if len(participants) >= 3:
        try:
            await query.answer("❌ Максимум участников!", show_alert=True)
        except:
            pass
        return
    
    # Вычисляем процент
    percent_per_person = order['percentage'] // 3
    remainder = order['percentage'] % 3
    
    if len(participants) == 0:
        percent_per_person += remainder
    
    # Добавляем участника
    participants.append({
        'user_id': user_id,
        'username': user_name,
        'percentage_per_person': percent_per_person
    })
    
    update_order_participants(order_id, participants)
    
    # Обновляем сообщение
    keyboard = [
        [InlineKeyboardButton(f"✅ Участвую ({len(participants)}/3)", callback_data=f'join_{order_id}')],
        [InlineKeyboardButton(f"❌ Отказ", callback_data=f'decline_{order_id}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    participant_list = ""
    for i, p in enumerate(participants, 1):
        participant_list += f"{i}. 👤 {p['username']} — {p['percentage_per_person']}%\n"
    
    message_text = (
        f"🎯 **НОВЫЙ ЗАКАЗ**\n\n"
        f"📌 Услуга: `{order['service_type']}`\n"
        f"🏦 Карта: `{order['card_number']}`\n"
        f"💰 Сумма: `{order['amount']}` кк\n"
        f"📊 Доход: `{order['percentage']}%`\n"
        f"👥 Участников: `{len(participants)}/3`\n\n"
        f"**Участники:**\n{participant_list}\n"
        f"🔑 ID: `{order_id}`"
    )
    
    try:
        await query.edit_message_text(
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except:
        pass
    
    try:
        await query.answer(
            f"✅ Добро пожаловать! {percent_per_person}% для вас",
            show_alert=True
        )
    except:
        pass

async def decline_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отказаться от заказа"""
    query = update.callback_query
    try:
        await query.answer("❌ Вы отказались", show_alert=True)
    except:
        pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "❓ **СПРАВКА**\n\n"
        "/start - Меню\n"
        "/help - Справка\n"
        "/profile - Профиль\n\n"
        "**Функции:**\n"
        "📝 Создание заказов\n"
        "👥 Коллаборация\n"
        "💰 Заработки\n"
        "⭐ Рейтинг"
    )
    
    if update.message:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile"""
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)
    
    if not stats:
        await update.message.reply_text("❌ Профиль не найден")
        return
    
    profile_text = (
        f"👤 **ПРОФИЛЬ**\n\n"
        f"ID: `{user_id}`\n"
        f"📊 Заказов: {stats['total_orders']}\n"
        f"✅ Завершено: {stats['completed_orders']}\n"
        f"💰 Заработано: {stats['total_earned']:.0f}%\n"
        f"⭐ Рейтинг: {stats['rating']:.1f}/5.0"
    )
    
    await update.message.reply_text(profile_text, parse_mode='Markdown')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(msg="Ошибка:", exc_info=context.error)

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
    
    logger.info(f"✅ Запуск с ADMIN_ID={ADMIN_ID}, GROUP_ID={GROUP_ID}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern='^create_order$')],
        states={
            SERVICE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_service_type)],
            CARD_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card_number)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            PERCENTAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_percentage)],
        },
        fallbacks=[CommandHandler('start', start)],
        per_message=False
    )
    
    # Обработчики
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('profile', profile_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CallbackQueryHandler(join_order, pattern='^join_'))
    app.add_handler(CallbackQueryHandler(decline_order, pattern='^decline_'))
    
    app.add_error_handler(error_handler)
    
    logger.info("✅ Бот готов к работе!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
