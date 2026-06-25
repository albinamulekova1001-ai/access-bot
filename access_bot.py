#!/usr/bin/env python3
"""
ACCESS Members Bot - закрытый платный канал
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8902228970:AAEeWIBIzjuvAPsdvOoyF2pEhLKN8d6rmRg"
ADMIN_ID = 479474184
CHANNEL_ID = -1004449691102
SUBSCRIPTION_PRICE = 2990
SUBSCRIPTION_MONTHS = 1
MANAGER_PHONE = "+7 999 838-01-35"

DB_FILE = "access_club.db"

class ApplicationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_comment = State()

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        name TEXT,
        comment TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        approved_at TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        name TEXT,
        status TEXT DEFAULT 'approved',
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_status TEXT DEFAULT 'pending'
    )
    ''')
    
    conn.commit()
    conn.close()

def get_app_status(user_id: int) -> Optional[dict]:
    """Получить статус заявки пользователя"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM applications WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'id': result[0],
            'user_id': result[1],
            'name': result[3],
            'comment': result[4],
            'status': result[5],
            'created_at': result[6]
        }
    return None

def save_application(user_id: int, username: str, name: str, comment: str):
    """Сохранить заявку в БД"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
        INSERT INTO applications (user_id, username, name, comment, status)
        VALUES (?, ?, ?, ?, 'pending')
        ''', (user_id, username, name, comment))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def approve_application(user_id: int):
    """Одобрить заявку"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE applications 
    SET status = 'approved', approved_at = CURRENT_TIMESTAMP
    WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def reject_application(user_id: int):
    """Отклонить заявку"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE applications 
    SET status = 'rejected'
    WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def confirm_subscription(user_id: int, name: str):
    """Подтвердить оплату и создать подписку"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    expires_at = datetime.now() + timedelta(days=30 * SUBSCRIPTION_MONTHS)
    
    cursor.execute('''
    INSERT OR REPLACE INTO subscriptions (user_id, name, status, expires_at, payment_status)
    VALUES (?, ?, 'active', ?, 'paid')
    ''', (user_id, name, expires_at))
    
    conn.commit()
    conn.close()

def get_keyboard_for_user(user_id: int):
    """Получить правильную клавиатуру в зависимости от статуса"""
    app = get_app_status(user_id)
    
    if app and app['status'] == 'approved':
        # После одобрения - только две кнопки
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💳 Оплатить подписку")],
                [KeyboardButton(text="📞 Связаться с менеджером")],
            ],
            resize_keyboard=True
        )
    else:
        # До одобрения - основное меню
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📝 Подать заявку")],
                [KeyboardButton(text="📊 Мой статус")],
            ],
            resize_keyboard=True
        )

def get_admin_keyboard(user_id: int):
    """Клавиатура для админа при просмотре заявки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ]
    )

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start"""
    await state.clear()
    
    app_status = get_app_status(message.from_user.id)
    
    welcome_text = "🎯 Добро пожаловать в ACCESS - закрытый клуб поставщиков!\n\n"
    
    if app_status:
        if app_status['status'] == 'pending':
            welcome_text += f"📋 Ваша заявка на рассмотрении...\n"
        elif app_status['status'] == 'approved':
            welcome_text += f"✅ Ваша заявка одобрена! Выберите действие ниже.\n"
        elif app_status['status'] == 'rejected':
            welcome_text += f"❌ К сожалению, ваша заявка отклонена.\n"
    else:
        welcome_text += "Подайте заявку чтобы присоединиться к нам!"
    
    await message.answer(welcome_text, reply_markup=get_keyboard_for_user(message.from_user.id))

@dp.message(F.text == "📝 Подать заявку")
async def start_application(message: types.Message, state: FSMContext):
    """Начать процесс подачи заявки"""
    app_status = get_app_status(message.from_user.id)
    
    if app_status and app_status['status'] in ['pending', 'approved']:
        await message.answer(
            "❌ У вас уже есть активная заявка или одобрение.\n"
            "Вы не можете подать новую заявку."
        )
        return
    
    await state.set_state(ApplicationForm.waiting_for_name)
    await message.answer(
        "📝 Введите ваше имя или название компании:",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отменить")]], resize_keyboard=True)
    )

@dp.message(ApplicationForm.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    """Обработка имени"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Заявка отменена", reply_markup=get_keyboard_for_user(message.from_user.id))
        return
    
    await state.update_data(name=message.text)
    await state.set_state(ApplicationForm.waiting_for_comment)
    await message.answer("💬 Добавьте комментарий (или напишите '-' если нет):")

@dp.message(ApplicationForm.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext):
    """Обработка комментария и сохранение заявки"""
    data = await state.get_data()
    name = data.get('name')
    comment = message.text if message.text != '-' else ""
    
    username = message.from_user.username or "без username"
    user_id = message.from_user.id
    
    if save_application(user_id, username, name, comment):
        await state.clear()
        await message.answer(
            "✅ Спасибо! Ваша заявка принята.\n"
            "Владелец канала рассмотрит её.",
            reply_markup=get_keyboard_for_user(user_id)
        )
        
        app_text = f"""
🔔 НОВАЯ ЗАЯВКА

👤 Имя: {name}
💬 Комментарий: {comment if comment else '(нет)'}
👨‍💻 Username: @{username}
🆔 User ID: {user_id}
⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
        await bot.send_message(ADMIN_ID, app_text, reply_markup=get_admin_keyboard(user_id))
    else:
        await state.clear()
        await message.answer(
            "❌ Вы уже подали заявку. Дождитесь рассмотрения.",
            reply_markup=get_keyboard_for_user(user_id)
        )

@dp.message(F.text == "📊 Мой статус")
async def check_status(message: types.Message):
    """Проверить статус заявки"""
    user_id = message.from_user.id
    app_status = get_app_status(user_id)
    
    if not app_status:
        await message.answer(
            "📋 У вас нет заявки.",
            reply_markup=get_keyboard_for_user(user_id)
        )
        return
    
    status_emoji = {'pending': '⏳', 'approved': '✅', 'rejected': '❌'}
    status_text = {'pending': 'На рассмотрении', 'approved': 'Одобрена', 'rejected': 'Отклонена'}
    
    emoji = status_emoji.get(app_status['status'], '❓')
    text = f"""
{emoji} Статус: {status_text[app_status['status']]}

👤 Имя: {app_status['name']}
💬 Комментарий: {app_status['comment'] if app_status['comment'] else '(нет)'}
📅 Дата: {app_status['created_at']}
"""
    
    if app_status['status'] == 'approved':
        text += f"\n💳 Подписка: ₽{SUBSCRIPTION_PRICE}/месяц"
    
    await message.answer(text, reply_markup=get_keyboard_for_user(user_id))

@dp.message(F.text == "💳 Оплатить подписку")
async def pay_message(message: types.Message):
    """Оплата подписки"""
    user_id = message.from_user.id
    app = get_app_status(user_id)
    
    if not app or app['status'] != 'approved':
        await message.answer("❌ Ваша заявка не одобрена", reply_markup=get_keyboard_for_user(user_id))
        return
    
    text = f"""💳 ОПЛАТА ПОДПИСКИ

Сумма: ₽{SUBSCRIPTION_PRICE}
Период: {SUBSCRIPTION_MONTHS} месяц(ев)

Платеж в обработке...
Владелец подтвердит платеж."""
    
    await message.answer(text, reply_markup=get_keyboard_for_user(user_id))
    
    text_admin = f"💰 ПЛАТЕЖ ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ\n\n"
    text_admin += f"👤 Пользователь: {app['name']}\n"
    text_admin += f"🆔 User ID: {user_id}\n"
    text_admin += f"💵 Сумма: ₽{SUBSCRIPTION_PRICE}\n\n"
    text_admin += f"Команда: `/confirm {user_id}`"
    
    await bot.send_message(ADMIN_ID, text_admin, parse_mode="Markdown")

@dp.message(F.text == "📞 Связаться с менеджером")
async def contact_manager(message: types.Message):
    """Контакт менеджера"""
    text = f"""📞 КОНТАКТ МЕНЕДЖЕРА

Телефон: {MANAGER_PHONE}

Напишите или позвоните для информации."""
    
    await message.answer(text, reply_markup=get_keyboard_for_user(message.from_user.id))

@dp.callback_query(F.data.startswith("approve_"))
async def approve_callback(query: types.CallbackQuery):
    """Одобрить заявку"""
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(query.data.split('_')[1])
    approve_application(user_id)
    
    await query.message.edit_text(query.message.text + "\n\n✅ ОДОБРЕНО")
    await query.answer("✅ Одобрено!", show_alert=True)
    
    try:
        app = get_app_status(user_id)
        text = f"""✅ Ваша заявка одобрена!

💳 Подписка: ₽{SUBSCRIPTION_PRICE}/месяц
⏱️ Период: {SUBSCRIPTION_MONTHS} месяц"""
        
        # Отправляем сообщение БЕЗ кнопок в тексте, только меню внизу
        await bot.send_message(user_id, text, reply_markup=get_keyboard_for_user(user_id))
    except Exception as e:
        print(f"Error: {e}")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_callback(query: types.CallbackQuery):
    """Отклонить заявку"""
    if query.from_user.id != ADMIN_ID:
        await query.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(query.data.split('_')[1])
    reject_application(user_id)
    
    await query.message.edit_text(query.message.text + "\n\n❌ ОТКЛОНЕНО")
    await query.answer("❌ Отклонено!", show_alert=True)
    
    try:
        await bot.send_message(user_id, "❌ Ваша заявка отклонена.")
    except Exception as e:
        print(f"Error: {e}")

@dp.message(Command("confirm"))
async def confirm_command(message: types.Message):
    """Подтверждение платежа"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещен")
        return
    
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Неверный формат. Используйте: /confirm USER_ID")
        return
    
    app = get_app_status(user_id)
    if not app:
        await message.answer("❌ Заявка не найдена")
        return
    
    confirm_subscription(user_id, app['name'])
    
    try:
        await bot.add_chat_member(CHANNEL_ID, user_id)
    except Exception as e:
        print(f"Error adding user: {e}")
    
    try:
        await bot.send_message(
            user_id,
            f"✅ ПЛАТЕЖ ПОДТВЕРЖДЕН!\n\n"
            f"🔗 Канал: https://t.me/c/{str(CHANNEL_ID).replace('-100', '')}\n\n"
            f"Подписка активна {SUBSCRIPTION_MONTHS} месяц(ев)."
        )
    except Exception as e:
        print(f"Error: {e}")
    
    await message.answer(f"✅ Подписка пользователя {user_id} активирована!")

@dp.message(Command("stats"))
async def stats_command(message: types.Message):
    """Статистика"""
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM applications WHERE status='pending'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM applications WHERE status='approved'")
    approved = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE status='active'")
    active = cursor.fetchone()[0]
    
    conn.close()
    
    text = f"""📊 СТАТИСТИКА
📋 На рассмотрении: {pending}
✅ Одобрено: {approved}
💳 Активные подписки: {active}"""
    
    await message.answer(text)

async def main():
    """Запуск бота"""
    init_db()
    print("✅ База данных инициализирована")
    print("🚀 Бот запускается...")
    
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
