import os
import logging
import sqlite3
import json
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from dotenv import load_dotenv
import aiofiles

# Load environment variables
load_dotenv()

# Bot token and admin IDs from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Multi-language support
LANGUAGES = {
    'english': {
        'welcome': '👋 Welcome to Proxy Selling Bot!\n\nChoose an option:',
        'main_menu': '🏠 Main Menu',
        'buy_proxy': '🛒 Buy Proxy',
        'prices': '💰 Prices',
        'my_proxies': '🔑 My Proxies',
        'balance': '💳 Balance',
        'support': '🆘 Support',
        'change_language': '🌐 Change Language',
        'invalid_command': '❗ Invalid command.',
        'select_package': 'Select a proxy package:',
        'one_proxy': 'One Proxy',
        'three_day': '3-Day Package',
        'seven_day': '7-Day Package',
        'monthly': 'Monthly Package',
        'payment_instructions': 'Please send payment to one of these methods:\n\n{methods}\n\nAfter payment, upload a screenshot as proof.',
        'payment_received': 'Payment proof received! Admin will review it shortly.',
        'current_balance': 'Your current balance: ${balance}',
        'top_up': '💳 Top Up',
        'history': '📋 History',
        'top_up_instructions': 'To top up your balance, send payment to one of these methods:\n\n{methods}\n\nAfter payment, upload a screenshot as proof.',
        'language_changed': 'Language changed to English.',
        'support_message': 'Please describe your issue and our support team will contact you shortly.',
        'support_request_sent': 'Support request sent! We will contact you soon.',
        'admin_panel': '👨‍💼 Admin Panel',
        'add_proxy': '➕ Add Proxy',
        'bulk_add_proxy': '📁 Bulk Add Proxy',
        'view_orders': '📋 View Orders',
        'set_price': '💰 Set Price',
        'payments': '💳 Payments',
        'broadcast': '📢 Broadcast',
        'backup_db': '💾 Backup DB',
        'turn_off': '🔴 Turn Off Bot',
        'turn_on': '🟢 Turn On Bot',
        'unauthorized': '❌ Unauthorized access.',
        'proxy_added': '✅ Proxy added successfully!',
        'invalid_proxy_format': '❌ Invalid proxy format. Use: IP:Port|Login|Pass|Country|Type',
        'bulk_proxy_result': '✅ Bulk proxy add completed:\nAdded: {added}\nSkipped: {skipped}',
        'order_approved': '✅ Order #{order_id} approved. Proxy assigned to user.',
        'order_cancelled': '❌ Order #{order_id} cancelled.',
        'price_updated': '✅ Price updated successfully!',
        'payment_methods_updated': '✅ Payment methods updated successfully!',
        'broadcast_sent': '✅ Broadcast sent to {count} users.',
        'db_backup_created': '✅ Database backup created.',
        'bot_turned_off': '✅ Bot turned off. Users will see maintenance message.',
        'bot_turned_on': '✅ Bot turned on. Bot is now operational.',
        'no_pending_orders': 'No pending orders.',
        'order_details': 'Order #{id}\nUser: @{username}\nPackage: {product}\nAmount: ${price}',
        'approve': '✅ Approve',
        'cancel': '❌ Cancel',
        'enter_price': 'Enter price for {package}:',
        'enter_payment_methods': 'Enter payment methods (one per line):',
        'enter_broadcast_message': 'Enter broadcast message:',
        'maintenance_mode': '🔧 Bot is under maintenance. Please try again later.'
    },
    'bangla': {
        'welcome': '👋 প্রক্সি বিক্রয় বটে স্বাগতম!\n\nএকটি বিকল্প চয়ন করুন:',
        'main_menu': '🏠 প্রধান মেনু',
        'buy_proxy': '🛒 প্রক্সি কিনুন',
        'prices': '💰 দাম',
        'my_proxies': '🔑 আমার প্রক্সি',
        'balance': '💳 ব্যালেন্স',
        'support': '🆘 সহায়তা',
        'change_language': '🌐 ভাষা পরিবর্তন',
        'invalid_command': '❗ ভুল কমান্ড।',
        'select_package': 'একটি প্রক্সি প্যাকেজ নির্বাচন করুন:',
        'one_proxy': 'একটি প্রক্সি',
        'three_day': '৩-দিনের প্যাকেজ',
        'seven_day': '৭-দিনের প্যাকেজ',
        'monthly': 'মাসিক প্যাকেজ',
        'payment_instructions': 'দয়া করে এই পদ্ধতিগুলোর একটিতে অর্থপ্রদান করুন:\n\n{methods}\n\nঅর্থপ্রদানের পর, প্রমাণ হিসেবে একটি স্ক্রিনশট আপলোড করুন।',
        'payment_received': 'পেমেন্ট প্রমাণ প্রাপ্ত! অ্যাডমিন শীঘ্রই এটি পর্যালোচনা করবে।',
        'current_balance': 'আপনার বর্তমান ব্যালেন্স: ${balance}',
        'top_up': '💳 টপ আপ',
        'history': '📋 ইতিহাস',
        'top_up_instructions': 'আপনার ব্যালেন্স টপ আপ করতে, এই পদ্ধতিগুলোর একটিতে অর্থপ্রদান করুন:\n\n{methods}\n\nঅর্থপ্রদানের পর, प्रमाण হিসেবে একটি স্ক্রিনশট আপলোড করুন।',
        'language_changed': 'ভাষা বাংলাতে পরিবর্তন করা হয়েছে।',
        'support_message': 'দয়া করে আপনার সমস্যাটি বর্ণনা করুন এবং আমাদের সহায়তা দল শীঘ্রই আপনার সাথে যোগাযোগ করবে।',
        'support_request_sent': 'সহায়তা অনুরোধ পাঠানো হয়েছে! আমরা শীঘ্রই আপনার সাথে যোগাযোগ করব।',
        'admin_panel': '👨‍💼 অ্যাডমিন প্যানেল',
        'add_proxy': '➕ প্রক্সি যোগ করুন',
        'bulk_add_proxy': '📁 বাল্ক প্রক্সি যোগ করুন',
        'view_orders': '📋 অর্ডার দেখুন',
        'set_price': '💰 দাম নির্ধারণ করুন',
        'payments': '💳 পেমেন্ট',
        'broadcast': '📢 ব্রডকাস্ট',
        'backup_db': '💾 ডিবি ব্যাকআপ',
        'turn_off': '🔴 বট বন্ধ করুন',
        'turn_on': '🟢 বট চালু করুন',
        'unauthorized': '❌ অননুমোদিত অ্যাক্সেস।',
        'proxy_added': '✅ প্রক্সি সফলভাবে যোগ করা হয়েছে!',
        'invalid_proxy_format': '❌ অবৈধ প্রক্সি ফরম্যাট। ব্যবহার করুন: IP:Port|Login|Pass|Country|Type',
        'bulk_proxy_result': '✅ বাল্ক প্রক্সি যোগ সম্পন্ন হয়েছে:\nযোগ করা হয়েছে: {added}\nবাদ দেওয়া হয়েছে: {skipped}',
        'order_approved': '✅ অর্ডার #{order_id} অনুমোদিত। ব্যবহারকারীকে প্রক্সি বরাদ্দ করা হয়েছে।',
        'order_cancelled': '❌ অর্ডার #{order_id} বাতিল করা হয়েছে।',
        'price_updated': '✅ দাম সফলভাবে আপডেট করা হয়েছে!',
        'payment_methods_updated': '✅ পেমেন্ট পদ্ধতি সফলভাবে আপডেট করা হয়েছে!',
        'broadcast_sent': '✅ ব্রডকাস্ট {count} ব্যবহারকারীর কাছে পাঠানো হয়েছে।',
        'db_backup_created': '✅ ডাটাবেস ব্যাকআপ তৈরি করা হয়েছে।',
        'bot_turned_off': '✅ বট বন্ধ করা হয়েছে। ব্যবহারকারীরা রক্ষণাবেক্ষণের বার্তা দেখতে পাবেন।',
        'bot_turned_on': '✅ বট চালু করা হয়েছে। বট এখন operational।',
        'no_pending_orders': 'কোনো বাকি অর্ডার নেই।',
        'order_details': 'অর্ডার #{id}\nব্যবহারকারী: @{username}\nপ্যাকেজ: {product}\nপরিমাণ: ${price}',
        'approve': '✅ অনুমোদন করুন',
        'cancel': '❌ বাতিল করুন',
        'enter_price': '{package}-এর দাম লিখুন:',
        'enter_payment_methods': 'পেমেন্ট পদ্ধতি লিখুন (একটি করে লাইন):',
        'enter_broadcast_message': 'ব্রডকাস্ট বার্তা লিখুন:',
        'maintenance_mode': '🔧 বটটি রক্ষণাবেক্ষণের মধ্যে রয়েছে। পরে আবার চেষ্টা করুন।'
    },
    'hindi': {
        'welcome': '👋 प्रॉक्सी सेलिंग बॉट में आपका स्वागत है!\n\nएक विकल्प चुनें:',
        'main_menu': '🏠 मुख्य मेनू',
        'buy_proxy': '🛒 प्रॉक्सी खरीदें',
        'prices': '💰 कीमतें',
        'my_proxies': '🔑 मेरे प्रॉक्सी',
        'balance': '💳 बैलेंस',
        'support': '🆘 सहायता',
        'change_language': '🌐 भाषा बदलें',
        'invalid_command': '❗ अमान्य कमांड।',
        'select_package': 'एक प्रॉक्सी पैकेज चुनें:',
        'one_proxy': 'एक प्रॉक्सी',
        'three_day': '3-दिन का पैकेज',
        'seven_day': '7-दिन का पैकेज',
        'monthly': 'मासिक पैकेज',
        'payment_instructions': 'कृपया इनमें से किसी एक विधि से भुगतान करें:\n\n{methods}\n\nभुगतान के बाद, प्रमाण के रूप में एक स्क्रीनशॉट अपलोड करें।',
        'payment_received': 'भुगतान प्रमाण प्राप्त! व्यवस्थापक इसे शीघ्र ही समीक्षा करेगा।',
        'current_balance': 'आपका वर्तमान बैलेंस: ${balance}',
        'top_up': '💳 टॉप अप',
        'history': '📋 इतिहास',
        'top_up_instructions': 'अपना बैलेंस टॉप अप करने के लिए, इनमें से किसी एक विधि से भुगतान करें:\n\n{methods}\n\nभुगतान के बाद, प्रमाण के रूप में एक स्क्रीनशॉट अपलोड करें।',
        'language_changed': 'भाषा हिंदी में बदल गई।',
        'support_message': 'कृपया अपनी समस्या का वर्णन करें और हमारी सहायता टीम शीघ्र ही आपसे संपर्क करेगी।',
        'support_request_sent': 'सहायता अनुरोध भेजा गया! हम जल्द ही आपसे संपर्क करेंगे।',
        'admin_panel': '👨‍💼 व्यवस्थापक पैनल',
        'add_proxy': '➕ प्रॉक्सी जोड़ें',
        'bulk_add_proxy': '📁 बल्क प्रॉक्सी जोड़ें',
        'view_orders': '📋 ऑर्डर देखें',
        'set_price': '💰 कीमत सेट करें',
        'payments': '💳 भुगतान',
        'broadcast': '📢 प्रसारण',
        'backup_db': '💾 डीबी बैकअप',
        'turn_off': '🔴 बॉट बंद करें',
        'turn_on': '🟢 बॉट चालू करें',
        'unauthorized': '❌ अनधिकृत पहुंच।',
        'proxy_added': '✅ प्रॉक्सी सफलतापूर्वक जोड़ा गया!',
        'invalid_proxy_format': '❌ अमान्य प्रॉक্সी प्रारूप। उपयोग करें: IP:Port|Login|Pass|Country|Type',
        'bulk_proxy_result': '✅ बल्क प्रॉक्सी जोड़ना पूरा हुआ:\nजोड़े गए: {added}\nछोड़े गए: {skipped}',
        'order_approved': '✅ ऑर्डर #{order_id} स्वीकृत। उपयोगकर्ता को प्रॉक्सी असाइन की गई।',
        'order_cancelled': '❌ ऑर्डर #{order_id} रद्द किया गया।',
        'price_updated': '✅ कीमत सफलतापूर्वक अपडेट की गई!',
        'payment_methods_updated': '✅ भुगतान विधियाँ सफलतापूर्वक अपडेट की गईं!',
        'broadcast_sent': '✅ प्रसारण {count} उपयोगकर्ताओं को भेजा गया।',
        'db_backup_created': '✅ डेटाबेस बैकअप बनाया गया।',
        'bot_turned_off': '✅ बॉट बंद कर दिया गया। उपयोगकर्ता रखरखाव संदेश देखेंगे।',
        'bot_turned_on': '✅ बॉट चालू कर दिया गया। बॉट अब operational है।',
        'no_pending_orders': 'कोई लंबित ऑर्डर नहीं।',
        'order_details': 'ऑर्डर #{id}\nउपयोगकर्ता: @{username}\nपैकेज: {product}\nराशि: ${price}',
        'approve': '✅ स्वीकार करें',
        'cancel': '❌ रद्द करें',
        'enter_price': '{package} के लिए कीमत दर्ज करें:',
        'enter_payment_methods': 'भुगतान विधियाँ दर्ज करें (एक पंक्ति में एक):',
        'enter_broadcast_message': 'प्रसारण संदेश दर्ज करें:',
        'maintenance_mode': '🔧 बॉट रखरखाव में है। कृपया बाद में पुन: प्रयास करें।'
    }
}

# Database setup
def init_db():
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        balance REAL DEFAULT 0,
        language TEXT DEFAULT 'english',
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Proxies table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS proxies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        port INTEGER,
        login TEXT,
        password TEXT,
        country TEXT,
        type TEXT,
        status TEXT DEFAULT 'available',
        order_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Orders table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product TEXT,
        price REAL,
        status TEXT DEFAULT 'pending',
        payment_proof_photo TEXT,
        assigned_proxy_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Admin logs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Price list table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS price_list (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        package_name TEXT UNIQUE,
        price REAL,
        currency TEXT DEFAULT 'USD'
    )
    ''')

    # Support tickets table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        language TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Payment methods table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payment_methods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        method TEXT,
        details TEXT
    )
    ''')

    # Bot settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE,
        setting_value TEXT
    )
    ''')

    # Insert default prices if not exists
    default_prices = [
        ('one_proxy', 2.0),
        ('three_day', 5.0),
        ('seven_day', 10.0),
        ('monthly', 30.0)
    ]

    for package, price in default_prices:
        cursor.execute('''
        INSERT OR IGNORE INTO price_list (package_name, price)
        VALUES (?, ?)
        ''', (package, price))

    # Insert default payment methods if not exists
    default_methods = [
        ('BTC', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'),
        ('USDT', '0x742d35Cc6634C0532925a3b844Bc454e4438f44e'),
        ('Bank Transfer', 'Account: 1234567890, Name: John Doe')
    ]

    for method, details in default_methods:
        cursor.execute('''
        INSERT OR IGNORE INTO payment_methods (method, details)
        VALUES (?, ?)
        ''', (method, details))

    # Insert default bot settings if not exists
    cursor.execute('''
    INSERT OR IGNORE INTO bot_settings (setting_key, setting_value)
    VALUES ('bot_active', 'true')
    ''')

    conn.commit()
    conn.close()

# Get user language
def get_user_language(telegram_id):
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM users WHERE telegram_id = ?', (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'english'

# Get text in user's language
def get_text(telegram_id, text_key, **kwargs):
    lang = get_user_language(telegram_id)
    text = LANGUAGES[lang].get(text_key, LANGUAGES['english'].get(text_key, text_key))
    return text.format(**kwargs) if kwargs else text

# Check if bot is active
def is_bot_active():
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT setting_value FROM bot_settings WHERE setting_key = "bot_active"')
    result = cursor.fetchone()
    conn.close()
    return result[0] == 'true' if result else True

# Log admin action
def log_admin_action(admin_id, action, details):
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO admin_logs (admin_id, action, details) VALUES (?, ?, ?)',
                  (admin_id, action, details))
    conn.commit()
    conn.close()

# States for FSM
class Form(StatesGroup):
    waiting_for_proxy = State()
    waiting_for_bulk_proxies = State()
    waiting_for_price = State()
    waiting_for_payment_methods = State()
    waiting_for_broadcast = State()
    waiting_for_support = State()
    waiting_for_payment_proof = State()
    waiting_for_top_up_proof = State()

# Start command
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (message.from_user.id,))
    user = cursor.fetchone()

    if not user:
        # Register new user
        cursor.execute('INSERT INTO users (telegram_id, username) VALUES (?, ?)',
                      (message.from_user.id, message.from_user.username))
        conn.commit()

    conn.close()

    # Create main menu keyboard
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(get_text(message.from_user.id, 'buy_proxy'), callback_data='buy_proxy'),
        InlineKeyboardButton(get_text(message.from_user.id, 'prices'), callback_data='prices'),
        InlineKeyboardButton(get_text(message.from_user.id, 'my_proxies'), callback_data='my_proxies'),
        InlineKeyboardButton(get_text(message.from_user.id, 'balance'), callback_data='balance'),
        InlineKeyboardButton(get_text(message.from_user.id, 'support'), callback_data='support'),
        InlineKeyboardButton(get_text(message.from_user.id, 'change_language'), callback_data='change_language')
    ]
    keyboard.add(*buttons)

    await message.answer(get_text(message.from_user.id, 'welcome'), reply_markup=keyboard)

# Language command
@dp.message_handler(commands=['lang'])
async def cmd_lang(message: types.Message):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    args = message.get_args().lower()
    if args in ['english', 'bangla', 'hindi']:
        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET language = ? WHERE telegram_id = ?',
                      (args, message.from_user.id))
        conn.commit()
        conn.close()

        await message.answer(get_text(message.from_user.id, 'language_changed'))
    else:
        await message.answer(get_text(message.from_user.id, 'invalid_command'))

# Buy command
@dp.message_handler(commands=['buy'])
async def cmd_buy(message: types.Message):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(get_text(message.from_user.id, 'one_proxy'), callback_data='package_one_proxy'),
        InlineKeyboardButton(get_text(message.from_user.id, 'three_day'), callback_data='package_three_day'),
        InlineKeyboardButton(get_text(message.from_user.id, 'seven_day'), callback_data='package_seven_day'),
        InlineKeyboardButton(get_text(message.from_user.id, 'monthly'), callback_data='package_monthly')
    ]
    keyboard.add(*buttons)

    await message.answer(get_text(message.from_user.id, 'select_package'), reply_markup=keyboard)

# Balance command
@dp.message_handler(commands=['balance'])
async def cmd_balance(message: types.Message):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE telegram_id = ?', (message.from_user.id,))
    balance = cursor.fetchone()[0]
    conn.close()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(get_text(message.from_user.id, 'top_up'), callback_data='top_up'),
        InlineKeyboardButton(get_text(message.from_user.id, 'history'), callback_data='history')
    )

    await message.answer(get_text(message.from_user.id, 'current_balance', balance=balance), reply_markup=keyboard)

# Support command
@dp.message_handler(commands=['support'])
async def cmd_support(message: types.Message, state: FSMContext):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    await message.answer(get_text(message.from_user.id, 'support_message'))
    await state.set_state(Form.waiting_for_support)

# Admin command
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    if message.from_user.id not in ADMIN_IDS:
        await message.answer(get_text(message.from_user.id, 'unauthorized'))
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(get_text(message.from_user.id, 'add_proxy'), callback_data='admin_add_proxy'),
        InlineKeyboardButton(get_text(message.from_user.id, 'bulk_add_proxy'), callback_data='admin_bulk_add_proxy'),
        InlineKeyboardButton(get_text(message.from_user.id, 'view_orders'), callback_data='admin_view_orders'),
        InlineKeyboardButton(get_text(message.from_user.id, 'set_price'), callback_data='admin_set_price'),
        InlineKeyboardButton(get_text(message.from_user.id, 'payments'), callback_data='admin_payments'),
        InlineKeyboardButton(get_text(message.from_user.id, 'broadcast'), callback_data='admin_broadcast'),
        InlineKeyboardButton(get_text(message.from_user.id, 'backup_db'), callback_data='admin_backup_db'),
        InlineKeyboardButton(get_text(message.from_user.id, 'turn_off'), callback_data='admin_turn_off'),
        InlineKeyboardButton(get_text(message.from_user.id, 'turn_on'), callback_data='admin_turn_on')
    ]
    keyboard.add(*buttons)

    await message.answer(get_text(message.from_user.id, 'admin_panel'), reply_markup=keyboard)

# Callback query handler
@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if not is_bot_active():
        lang = get_user_language(user_id)
        await bot.answer_callback_query(callback_query.id, LANGUAGES[lang]['maintenance_mode'])
        return

    # Handle package selection
    if data.startswith('package_'):
        package = data.replace('package_', '')

        # Get package price
        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT price FROM price_list WHERE package_name = ?', (package,))
        price = cursor.fetchone()[0]
        conn.close()

        # Create order
        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO orders (user_id, product, price) VALUES (?, ?, ?)',
                      (user_id, package, price))
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Get payment methods
        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT method, details FROM payment_methods')
        methods = cursor.fetchall()
        conn.close()

        # Format payment methods
        methods_text = "\n".join([f"{method}: {details}" for method, details in methods])

        await bot.send_message(
            user_id,
            get_text(user_id, 'payment_instructions', methods=methods_text)
        )
        await state.set_state(Form.waiting_for_payment_proof)
        await state.update_data(order_id=order_id)

    # Handle top up
    elif data == 'top_up':
        # Get payment methods
        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT method, details FROM payment_methods')
        methods = cursor.fetchall()
        conn.close()

        # Format payment methods
        methods_text = "\n".join([f"{method}: {details}" for method, details in methods])

        await bot.send_message(
            user_id,
            get_text(user_id, 'top_up_instructions', methods=methods_text)
        )
        await state.set_state(Form.waiting_for_top_up_proof)

    # Handle admin actions
    elif data.startswith('admin_'):
        if user_id not in ADMIN_IDS:
            await bot.answer_callback_query(callback_query.id, get_text(user_id, 'unauthorized'))
            return

        action = data.replace('admin_', '')

        if action == 'add_proxy':
            await bot.send_message(user_id, "Send proxy in format: IP:Port|Login|Pass|Country|Type")
            await state.set_state(Form.waiting_for_proxy)

        elif action == 'bulk_add_proxy':
            await bot.send_message(user_id, "Send a TXT or CSV file with proxies (one per line)")
            await state.set_state(Form.waiting_for_bulk_proxies)

        elif action == 'view_orders':
            conn = sqlite3.connect('proxy_bot.db')
            cursor = conn.cursor()
            cursor.execute('''
            SELECT o.id, o.user_id, u.username, o.product, o.price, o.payment_proof_photo
            FROM orders o
            JOIN users u ON o.user_id = u.telegram_id
            WHERE o.status = 'pending'
            ''')
            orders = cursor.fetchall()
            conn.close()

            admin_id = callback_query.from_user.id
            if not orders:
                await bot.send_message(admin_id, get_text(admin_id, 'no_pending_orders'))
                return

            for order in orders:
                order_id, customer_id, username, product, price, proof_photo = order

                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(get_text(admin_id, 'approve'), callback_data=f'approve_{order_id}'),
                    InlineKeyboardButton(get_text(admin_id, 'cancel'), callback_data=f'cancel_{order_id}')
                )

                await bot.send_message(
                    admin_id,
                    get_text(admin_id, 'order_details', id=order_id, username=username, product=product, price=price)
                )

                if proof_photo:
                    await bot.send_photo(admin_id, proof_photo, reply_markup=keyboard)
                else:
                    await bot.send_message(admin_id, "No payment proof", reply_markup=keyboard)

        elif action == 'set_price':
            conn = sqlite3.connect('proxy_bot.db')
            cursor = conn.cursor()
            cursor.execute('SELECT package_name FROM price_list')
            packages = [row[0] for row in cursor.fetchall()]
            conn.close()

            keyboard = InlineKeyboardMarkup()
            for package in packages:
                keyboard.add(InlineKeyboardButton(
                    get_text(user_id, package),
                    callback_data=f'set_price_{package}'
                ))

            await bot.send_message(user_id, "Select package to set price:", reply_markup=keyboard)

        elif action == 'payments':
            conn = sqlite3.connect('proxy_bot.db')
            cursor = conn.cursor()
            cursor.execute('SELECT method, details FROM payment_methods')
            methods = cursor.fetchall()
            conn.close()

            methods_text = "\n".join([f"{method}: {details}" for method, details in methods])
            await bot.send_message(user_id, f"Current payment methods:\n\n{methods_text}")
            await bot.send_message(user_id, get_text(user_id, 'enter_payment_methods'))
            await state.set_state(Form.waiting_for_payment_methods)

        elif action == 'broadcast':
            await bot.send_message(user_id, get_text(user_id, 'enter_broadcast_message'))
            await state.set_state(Form.waiting_for_broadcast)

        elif action == 'backup_db':
            # Create backup
            backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            conn = sqlite3.connect('proxy_bot.db')
            conn.backup(sqlite3.connect(backup_filename))
            conn.close()

            # Send backup file
            await bot.send_document(user_id, InputFile(backup_filename))
            os.remove(backup_filename)

            log_admin_action(user_id, 'backup_db', 'Database backup created')
            await bot.send_message(user_id, get_text(user_id, 'db_backup_created'))

        elif action == 'turn_off':
            conn = sqlite3.connect('proxy_bot.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE bot_settings SET setting_value = "false" WHERE setting_key = "bot_active"')
            conn.commit()
            conn.close()

            log_admin_action(user_id, 'turn_off', 'Bot turned off')
            await bot.send_message(user_id, get_text(user_id, 'bot_turned_off'))

        elif action == 'turn_on':
            conn = sqlite3.connect('proxy_bot.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE bot_settings SET setting_value = "true" WHERE setting_key = "bot_active"')
            conn.commit()
            conn.close()

            log_admin_action(user_id, 'turn_on', 'Bot turned on')
            await bot.send_message(user_id, get_text(user_id, 'bot_turned_on'))

    # Handle order approval/cancellation
    elif data.startswith('approve_') or data.startswith('cancel_'):
        order_id = int(data.split('_')[1])
        is_approve = data.startswith('approve_')

        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()

        if is_approve:
            # Get order details
            cursor.execute('SELECT user_id, product, price FROM orders WHERE id = ?', (order_id,))
            order = cursor.fetchone()
            user_id, product, price = order

            # Get available proxy
            cursor.execute('SELECT id, ip, port, login, password, country, type FROM proxies WHERE status = "available" LIMIT 1')
            proxy = cursor.fetchone()

            if proxy:
                proxy_id, ip, port, login, password, country, proxy_type = proxy

                # Assign proxy to order
                cursor.execute('UPDATE orders SET status = "completed", assigned_proxy_id = ? WHERE id = ?',
                              (proxy_id, order_id))

                # Update proxy status
                cursor.execute('UPDATE proxies SET status = "sold", order_id = ? WHERE id = ?',
                              (order_id, proxy_id))

                # Update user balance
                cursor.execute('UPDATE users SET balance = balance - ? WHERE telegram_id = ?',
                              (price, user_id))

                conn.commit()

                # Send proxy details to user
                proxy_details = f"Your proxy details:\nIP: {ip}\nPort: {port}\nLogin: {login}\nPassword: {password}\nCountry: {country}\nType: {proxy_type}"
                await bot.send_message(user_id, proxy_details)

                # Notify admin
                await bot.send_message(callback_query.from_user.id,
                                     get_text(callback_query.from_user.id, 'order_approved', order_id=order_id))

                log_admin_action(callback_query.from_user.id, 'approve_order', f'Order #{order_id} approved')
            else:
                await bot.send_message(callback_query.from_user.id, "No available proxies")
        else:
            # Cancel order
            cursor.execute('UPDATE orders SET status = "cancelled" WHERE id = ?', (order_id,))
            conn.commit()

            # Notify admin
            await bot.send_message(callback_query.from_user.id,
                                 get_text(callback_query.from_user.id, 'order_cancelled', order_id=order_id))

            log_admin_action(callback_query.from_user.id, 'cancel_order', f'Order #{order_id} cancelled')

        conn.close()

    # Handle price setting
    elif data.startswith('set_price_'):
        package = data.replace('set_price_', '')
        await state.update_data(price_package=package)
        await bot.send_message(user_id, get_text(user_id, 'enter_price', package=package))
        await state.set_state(Form.waiting_for_price)

    await bot.answer_callback_query(callback_query.id)

# Handle payment proof photo
@dp.message_handler(content_types=types.ContentType.PHOTO, state=Form.waiting_for_payment_proof)
async def process_payment_proof(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    order_id = user_data.get('order_id')

    if order_id:
        # Save payment proof to order
        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET payment_proof_photo = ? WHERE id = ?',
                      (message.photo[-1].file_id, order_id))
        conn.commit()
        conn.close()

        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup()
                keyboard.add(
                    InlineKeyboardButton(get_text(admin_id, 'approve'), callback_data=f'approve_{order_id}'),
                    InlineKeyboardButton(get_text(admin_id, 'cancel'), callback_data=f'cancel_{order_id}')
                )

                await bot.send_message(admin_id, f"New payment proof for order #{order_id}")
                await bot.send_photo(admin_id, message.photo[-1].file_id, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id}: {e}")

        await message.answer(get_text(message.from_user.id, 'payment_received'))
    else:
        await message.answer("Error processing payment proof")

    await state.clear()

# Handle top up proof photo
@dp.message_handler(content_types=types.ContentType.PHOTO, state=Form.waiting_for_top_up_proof)
async def process_top_up_proof(message: types.Message, state: FSMContext):
    # Notify admins about top-up request
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"Top-up request from user @{message.from_user.username}")
            await bot.send_photo(admin_id, message.photo[-1].file_id)
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

    await message.answer("Top-up request sent! Admin will process it shortly.")
    await state.clear()

# Handle support message
@dp.message_handler(state=Form.waiting_for_support)
async def process_support(message: types.Message, state: FSMContext):
    # Create support ticket
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO support_tickets (user_id, message, language) VALUES (?, ?, ?)',
                  (message.from_user.id, message.text, get_user_language(message.from_user.id)))
    conn.commit()
    conn.close()

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"New support ticket from @{message.from_user.username}:\n\n{message.text}")
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")

    await message.answer(get_text(message.from_user.id, 'support_request_sent'))
    await state.clear()

# Handle proxy input
@dp.message_handler(state=Form.waiting_for_proxy)
async def process_proxy(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    proxy_data = message.text.split('|')
    if len(proxy_data) != 5:
        await message.answer(get_text(message.from_user.id, 'invalid_proxy_format'))
        return

    ip_port = proxy_data[0].split(':')
    if len(ip_port) != 2:
        await message.answer(get_text(message.from_user.id, 'invalid_proxy_format'))
        return

    ip, port = ip_port
    login, password, country, proxy_type = proxy_data[1:]

    # Add proxy to database
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO proxies (ip, port, login, password, country, type) VALUES (?, ?, ?, ?, ?, ?)',
                  (ip, int(port), login, password, country, proxy_type))
    conn.commit()
    conn.close()

    log_admin_action(message.from_user.id, 'add_proxy', f'Added proxy: {message.text}')
    await message.answer(get_text(message.from_user.id, 'proxy_added'))
    await state.clear()

# Handle bulk proxies file
@dp.message_handler(content_types=types.ContentType.DOCUMENT, state=Form.waiting_for_bulk_proxies)
async def process_bulk_proxies(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    # Download file
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    await bot.download_file(file_path, "proxies.txt")

    # Process file
    added = 0
    skipped = 0

    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()

    async with aiofiles.open("proxies.txt", mode='r') as f:
        content = await f.read()
        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            proxy_data = line.split('|')
            if len(proxy_data) != 5:
                skipped += 1
                continue

            ip_port = proxy_data[0].split(':')
            if len(ip_port) != 2:
                skipped += 1
                continue

            try:
                ip, port = ip_port
                login, password, country, proxy_type = proxy_data[1:]

                cursor.execute('INSERT INTO proxies (ip, port, login, password, country, type) VALUES (?, ?, ?, ?, ?, ?)',
                              (ip, int(port), login, password, country, proxy_type))
                added += 1
            except:
                skipped += 1

    conn.commit()
    conn.close()

    os.remove("proxies.txt")

    log_admin_action(message.from_user.id, 'bulk_add_proxy', f'Added {added} proxies, skipped {skipped}')
    await message.answer(get_text(message.from_user.id, 'bulk_proxy_result', added=added, skipped=skipped))
    await state.clear()

# Handle price input
@dp.message_handler(state=Form.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    try:
        price = float(message.text)
        user_data = await state.get_data()
        package = user_data.get('price_package')

        conn = sqlite3.connect('proxy_bot.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE price_list SET price = ? WHERE package_name = ?', (price, package))
        conn.commit()
        conn.close()

        log_admin_action(message.from_user.id, 'set_price', f'Set price for {package} to {price}')
        await message.answer(get_text(message.from_user.id, 'price_updated'))
    except ValueError:
        await message.answer("Invalid price. Please enter a number.")

    await state.clear()

# Handle payment methods input
@dp.message_handler(state=Form.waiting_for_payment_methods)
async def process_payment_methods(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    # Clear existing methods
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM payment_methods')

    # Add new methods
    methods = message.text.split('\n')
    for method in methods:
        method = method.strip()
        if not method:
            continue

        if ':' in method:
            method_name, details = method.split(':', 1)
            cursor.execute('INSERT INTO payment_methods (method, details) VALUES (?, ?)',
                          (method_name.strip(), details.strip()))
        else:
            cursor.execute('INSERT INTO payment_methods (method) VALUES (?)', (method.strip(),))

    conn.commit()
    conn.close()

    log_admin_action(message.from_user.id, 'update_payment_methods', 'Updated payment methods')
    await message.answer(get_text(message.from_user.id, 'payment_methods_updated'))
    await state.clear()

# Handle broadcast message
@dp.message_handler(state=Form.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    # Get all users
    conn = sqlite3.connect('proxy_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT telegram_id, language FROM users')
    users = cursor.fetchall()
    conn.close()

    # Send broadcast to all users
    sent_count = 0
    for user_id, lang in users:
        try:
            # Try to send in user's language first
            if lang in LANGUAGES:
                # Check if we have a translation for broadcast message
                # For simplicity, we'll just send the original message
                await bot.send_message(user_id, message.text)
            else:
                await bot.send_message(user_id, message.text)
            sent_count += 1
        except Exception as e:
            logger.error(f"Error sending broadcast to {user_id}: {e}")

    log_admin_action(message.from_user.id, 'broadcast', f'Sent to {sent_count} users')
    await message.answer(get_text(message.from_user.id, 'broadcast_sent', count=sent_count))
    await state.clear()

# Handle invalid commands
@dp.message_handler()
async def handle_invalid_commands(message: types.Message):
    if not is_bot_active():
        lang = get_user_language(message.from_user.id)
        await message.answer(LANGUAGES[lang]['maintenance_mode'])
        return

    await message.answer(get_text(message.from_user.id, 'invalid_command'))

# Main function
if __name__ == '__main__':
    # Initialize database
    init_db()

    # Start the bot
    executor.start_polling(dp, skip_updates=True)
