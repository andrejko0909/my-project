import logging
import sqlite3
import pytz
import calendar
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# --- НАЛАШТУВАННЯ ---
API_TOKEN = 8754341576:AAHAn6MSHFYmIbgyAwtD5R4ngQ367EUvGKA
ADMIN_ID = 1459073476
TIMEZONE = pytz.timezone('Europe/Kyiv')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class Form(StatesGroup):
    name = State()
    phone = State()

# --- БАЗА ДАНИХ ---
def init_db():
    conn = sqlite3.connect('elena_business.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS busy_slots (date TEXT, time TEXT, info TEXT)')
    conn.commit()
    conn.close()

init_db()

# --- ЛОГІКА КНОПОК ---

def get_months_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    now = datetime.now(TIMEZONE)
    for i in range(3):
        m_date = now + timedelta(days=30*i)
        m_name = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень", "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"][m_date.month-1]
        kb.insert(types.InlineKeyboardButton(f"{m_name} {m_date.year}", callback_data=f"m_{m_date.month}_{m_date.year}"))
    return kb

def get_days_kb(month, year):
    kb = types.InlineKeyboardMarkup(row_width=5)
    now = datetime.now(TIMEZONE)
    _, last_day = calendar.monthrange(int(year), int(month))
    for day in range(1, last_day + 1):
        if int(year) == now.year and int(month) == now.month and day <= now.day:
            continue
        d_str = f"{day:02d}.{int(month):02d}"
        kb.insert(types.InlineKeyboardButton(str(day), callback_data=f"d_{d_str}"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_m"))
    return kb

def get_times_kb(date_str, is_admin=False):
    kb = types.InlineKeyboardMarkup(row_width=2)
    slots = ["10:00", "13:00", "16:00", "19:00"]
    conn = sqlite3.connect('elena_business.db')
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM busy_slots WHERE date = ?", (date_str,))
    busy = [r[0] for r in cursor.fetchall()]
    conn.close()

    for s in slots:
        if s in busy:
            if is_admin: 
                kb.insert(types.InlineKeyboardButton(f"🔴 Видалити {s}", callback_data=f"un_{date_str}_{s}"))
            else:
                continue
        else:
            cb = f"admbook_{date_str}_{s}" if is_admin else f"t_{date_str}_{s}"
            kb.insert(types.InlineKeyboardButton(s, callback_data=cb))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_m"))
    return kb

# --- ОБРОБНИКИ ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("📅 Записатися", "🕒 Графік")
    await message.answer("🌸 Вітаємо у Олени!", reply_markup=kb)
    if message.from_user.id == ADMIN_ID:
        adm_kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⚙️ Керування графіком", callback_data="adm_manage"))
        await message.answer("🛠 Ви адмін:", reply_markup=adm_kb)

@dp.message_handler(lambda m: m.text == "📅 Записатися")
async def start_book(message: types.Message):
    await message.answer("Оберіть місяць:", reply_markup=get_months_kb())

@dp.callback_query_handler(lambda c: c.data.startswith('m_'))
async def set_month(call: types.CallbackQuery):
    _, m, y = call.data.split('_')
    await call.message.edit_text(f"Місяць обрано. Тепер день:", reply_markup=get_days_kb(m, y))

@dp.callback_query_handler(lambda c: c.data == "back_m")
async def back_m(call: types.CallbackQuery):
    await call.message.edit_text("Оберіть місяць:", reply_markup=get_months_kb())

@dp.callback_query_handler(lambda c: c.data.startswith('d_'))
async def set_day(call: types.CallbackQuery):
    date = call.data.split('_')[1]
    await call.message.edit_text(f"Вільний час на {date}:", reply_markup=get_times_kb(date))

@dp.callback_query_handler(lambda c: c.data.startswith('t_'))
async def set_time(call: types.CallbackQuery, state: FSMContext):
    _, date, time = call.data.split('_')
    await state.update_data(date=date, time=time)
    await call.message.delete()
    await call.message.answer("Як вас звати?")
    await Form.name.set()

@dp.message_handler(state=Form.name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Ваш номер телефону:")
    await Form.phone.set()

@dp.message_handler(state=Form.phone)
async def get_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tag = f"@{message.from_user.username}" if message.from_user.username else "немає"
    info = f"Клієнт: {data['name']}, Тел: {message.text}, ТГ: {tag}"
    
    conn = sqlite3.connect('elena_business.db')
    conn.execute("INSERT INTO busy_slots VALUES (?, ?, ?)", (data['date'], data['time'], info))
    conn.commit()
    conn.close()
    
    await bot.send_message(ADMIN_ID, f"🔔 **НОВИЙ ЗАПИС!**\n📅 {data['date']} о {data['time']}\n👤 {info}")
    await message.answer(f"✅ Записано на {data['date']} о {data['time']}!")
    await state.finish()

# --- АДМІНКА ---
@dp.callback_query_handler(lambda c: c.data == "adm_manage")
async def adm_manage(call: types.CallbackQuery):
    await call.message.edit_text("Оберіть місяць для редагування:", reply_markup=get_months_kb())

@dp.callback_query_handler(lambda c: c.data.startswith('admbook_'))
async def adm_block(call: types.CallbackQuery):
    _, date, time = call.data.split('_')
    conn = sqlite3.connect('elena_business.db')
    conn.execute("INSERT INTO busy_slots VALUES (?, ?, ?)", (date, time, "ЗАБЛОКОВАНО АДМІНОМ"))
    conn.commit()
    await call.answer("Заблоковано!")
    await call.message.edit_text(f"Слот {date} {time} закрито.", reply_markup=get_times_kb(date, True))

@dp.callback_query_handler(lambda c: c.data.startswith('un_'))
async def adm_unblock(call: types.CallbackQuery):
    _, date, time = call.data.split('_')
    conn = sqlite3.connect('elena_business.db')
    conn.execute("DELETE FROM busy_slots WHERE date=? AND time=?", (date, time))
    conn.commit()
    await call.answer("Звільнено!")
    await call.message.edit_text(f"Слот {date} {time} відкрито.", reply_markup=get_times_kb(date, True))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
