# main.py
# Appointment booking Telegram bot (uses bot_config.py for token)
import os
import sqlite3
import threading
import random
from datetime import datetime
import telebot
from telebot import types

# import token from separate config file
from bot_config import TOKEN

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "appointments.db")

bot = telebot.TeleBot(TOKEN)

db_lock = threading.Lock()

def init_db():
    """Create the appointments table if it doesn't exist."""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            name TEXT,
            national_id TEXT,
            specialty TEXT,
            doctor TEXT,
            insurance TEXT,
            price INTEGER,
            visit_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()
        conn.close()
        print("DB initialized:", DB_PATH)

def save_appointment(chat_id, data):
    """Save a single appointment record to the DB."""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO appointments
                (chat_id, name, national_id, specialty, doctor, insurance, price, visit_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chat_id,
                data.get("name"),
                data.get("national_id"),
                data.get("specialty"),
                data.get("doctor"),
                data.get("insurance"),
                data.get("price"),
                data.get("code"),
                data.get("created_at")
            ))
            conn.commit()
            conn.close()
            print("✅ Saved appointment:", data)
    except Exception as e:
        import traceback
        print("❌ DB save error:", e)
        traceback.print_exc()
        raise

# ====== Bot data ======
specialties = {
    "گوش و حلق و بینی": ["دکتر نیوشا اصغری", "دکتر حسن رضایی"],
    "مغز و اعصاب": ["دکتر ماهور شمس", "دکتر سعید کرمی"],
    "پوست و مو": ["دکتر مریم عبدی", "دکتر احد کاظمی"],
    "فیزیوتراپی": ["دکتر رها غلامی", "دکتر سهیل نوربخش"]
}

user_sessions = {}

# ====== Keyboards ======
def specialties_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for s in specialties.keys():
        markup.add(types.KeyboardButton(s))
    return markup

def doctors_keyboard(specialty):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for d in specialties.get(specialty, []):
        markup.add(types.KeyboardButton(d))
    markup.add(types.KeyboardButton("🔙 بازگشت"))
    return markup

def insurance_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("تأمین اجتماعی"), types.KeyboardButton("نیروهای مسلح"))
    markup.add(types.KeyboardButton("آزاد"), types.KeyboardButton("سایر"))
    markup.add(types.KeyboardButton("🔙 بازگشت"))
    return markup

def payment_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("💳 پرداخت"), types.KeyboardButton("🔙 بازگشت"))
    return markup

# ====== Handlers ======
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_sessions.pop(chat_id, None)
    bot.send_message(chat_id, "سلام\nتخصص مورد نظر را انتخاب کنید:", reply_markup=specialties_keyboard())

@bot.message_handler(func=lambda m: m.text in specialties.keys())
def handle_specialty(message):
    chat_id = message.chat.id
    spec = message.text
    user_sessions[chat_id] = {"specialty": spec}
    bot.send_message(chat_id, f"شما تخصص {spec} را انتخاب کردید.\nلطفاً دکتر مورد نظر را انتخاب کنید:",
                     reply_markup=doctors_keyboard(spec))

@bot.message_handler(func=lambda m: m.text == "🔙 بازگشت")
def handle_back(message):
    chat_id = message.chat.id
    user_sessions.pop(chat_id, None)
    bot.send_message(chat_id, "بازگشت به منوی اصلی.", reply_markup=specialties_keyboard())

@bot.message_handler(func=lambda m: any(m.text in docs for docs in specialties.values()))
def handle_doctor(message):
    chat_id = message.chat.id
    text = message.text
    if text == "🔙 بازگشت":
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, "بازگشت به منوی اصلی.", reply_markup=specialties_keyboard())
        return

    sess = user_sessions.setdefault(chat_id, {})
    sess["doctor"] = text

    bot.send_message(chat_id, "لطفاً نام و نام‌خانوادگی خود را وارد کنید:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, get_name)

def get_name(message):
    chat_id = message.chat.id
    text = message.text
    if text == "🔙 بازگشت":
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, "بازگشت به منوی اصلی.", reply_markup=specialties_keyboard())
        return
    sess = user_sessions.setdefault(chat_id, {})
    sess["name"] = text.strip()
    bot.send_message(chat_id, "لطفاً کد ملی خود را وارد کنید (10 رقم):")
    bot.register_next_step_handler(message, get_national_id)

def get_national_id(message):
    chat_id = message.chat.id
    nid = message.text.strip() if message.text else ""
    if nid == "🔙 بازگشت":
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, "بازگشت به منوی اصلی.", reply_markup=specialties_keyboard())
        return

    if not nid.isdigit() or len(nid) != 10:
        bot.send_message(chat_id, "کد ملی نامعتبر است. لطفاً 10 رقم کد ملی را وارد کنید:")
        bot.register_next_step_handler(message, get_national_id)
        return

    sess = user_sessions.setdefault(chat_id, {})
    sess["national_id"] = nid

    bot.send_message(chat_id, "نوع بیمه خود را انتخاب کنید:", reply_markup=insurance_keyboard())
    bot.register_next_step_handler(message, get_insurance)

def get_insurance(message):
    chat_id = message.chat.id
    ins = message.text
    if ins == "🔙 بازگشت":
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, "بازگشت به منوی اصلی.", reply_markup=specialties_keyboard())
        return

    if ins not in ["تأمین اجتماعی", "نیروهای مسلح", "آزاد", "سایر"]:
        bot.send_message(chat_id, "لطفاً یکی از گزینه‌های بیمه را از کیبورد انتخاب کنید.")
        bot.register_next_step_handler(message, get_insurance)
        return

    sess = user_sessions.setdefault(chat_id, {})
    sess["insurance"] = ins

    price = random.randint(50000, 200000)  # in toman
    sess["price"] = price

    info = (
        f"👤 نام بیمار: {sess.get('name','-')}\n"
        f"🆔 کد ملی: {sess.get('national_id','-')}\n"
        f"🏥 تخصص: {sess.get('specialty','-')}\n"
        f"👨‍⚕️ دکتر: {sess.get('doctor','-')}\n"
        f"🪪 بیمه: {sess.get('insurance','-')}\n"
        f"💰 مبلغ: {price:,} تومان\n\n"
        "برای تکمیل و پرداخت روی دکمه پرداخت بزنید یا با بازگشت به صفحه قبل برگردید."
    )

    bot.send_message(chat_id, info, reply_markup=payment_keyboard())
    bot.register_next_step_handler(message, payment_step)

def payment_step(message):
    chat_id = message.chat.id
    text = message.text
    if text == "🔙 بازگشت":
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, "بازگشت به منوی اصلی.", reply_markup=specialties_keyboard())
        return

    if text == "💳 پرداخت":
        sess = user_sessions.get(chat_id)
        if not sess:
            bot.send_message(chat_id, "اطلاعات جلسه پیدا نشد. لطفاً مجدداً آغاز کنید (/start).", reply_markup=specialties_keyboard())
            return

        visit_code = str(random.randint(10000, 99999))
        sess["code"] = visit_code
        sess["created_at"] = datetime.now().isoformat()

        try:
            save_appointment(chat_id, sess)
        except Exception as e:
            bot.send_message(chat_id, "خطا در ذخیره‌سازی نوبت. لطفاً بعداً تلاش کنید.")
            print("DB save error (outer):", e)
            return

        bot.send_message(chat_id, f"✅ پرداخت با موفقیت انجام شد.\nکد مراجعه شما: {visit_code}\n\n"
                                  "لطفاً کد را تا زمان مراجعه نگهدارید.\n"
                                  "برای آغاز یک رزرو دیگر /start را وارد کنید.",
                         reply_markup=types.ReplyKeyboardRemove())

        user_sessions.pop(chat_id, None)
    else:
        bot.send_message(chat_id, "لطفاً از دکمه‌های زیر استفاده کنید.", reply_markup=payment_keyboard())
        bot.register_next_step_handler(message, payment_step)

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "لطفاً یکی از دکمه‌های موجود را انتخاب کنید یا /start را بزنید.", reply_markup=specialties_keyboard())

if __name__ == "__main__":
    print("robot start now ...")
    init_db()
    bot.infinity_polling()
