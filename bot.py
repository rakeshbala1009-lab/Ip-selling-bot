import sqlite3
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, CallbackContext
from telegram.ext import filters
import os
from datetime import datetime

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8146938965:AAFU1GnMhwz3k7TWrZsADHs2D1P_lPNkd3k"
ADMIN_IDS = [7568642311]  # Your admin ID
SUPPORTED_CURRENCIES = ["USD", "BDT"]
DEFAULT_CURRENCY = "BDT"

# Database setup
def init_db():
    conn = sqlite3.connect('socks5_bot.db')
    c = conn.cursor()
    # Users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0,
                 currency TEXT DEFAULT 'BDT', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')
    # Proxies table (with country support)
    c.execute('''
    CREATE TABLE IF NOT EXISTS proxies
                (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, port INTEGER,
                 username TEXT, password TEXT, country TEXT, is_sold BOOLEAN DEFAULT FALSE,
                sold_to INTEGER, sold_at TIMESTAMP)
    ''')
    # Payments table
    c.execute('''
    CREATE TABLE IF NOT EXISTS payments
                (id INTEGER PRIMARY KEY AUTOINCREMENT, method_name TEXT,
                 method_id TEXT, is_active BOOLEAN DEFAULT TRUE)
    ''')
    # Prices table (with currency support)
    c.execute('''
    CREATE TABLE IF NOT EXISTS prices
                (id INTEGER PRIMARY KEY AUTOINCREMENT, quantity INTEGER,
                 price REAL, currency TEXT)
    ''')
    # Deposits table (with approval system)
    c.execute('''
    CREATE TABLE IF NOT EXISTS deposits
                (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
                 method TEXT, proof TEXT, status TEXT DEFAULT 'pending',
                 admin_action_by INTEGER, admin_action_at TIMESTAMP,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    ''')
    # Insert default prices if not exists
    for currency in SUPPORTED_CURRENCIES:
        if currency == "BDT":
            c.execute("INSERT OR IGNORE INTO prices (quantity, price, currency) VALUES (1, 50, ?)", (currency,))
            c.execute("INSERT OR IGNORE INTO prices (quantity, price, currency) VALUES (3, 120, ?)", (currency,))
            c.execute("INSERT OR IGNORE INTO prices (quantity, price, currency) VALUES (5, 180, ?)", (currency,))
        elif currency == "USD":
            c.execute("INSERT OR IGNORE INTO prices (quantity, price, currency) VALUES (1, 0.5, ?)", (currency,))
            c.execute("INSERT OR IGNORE INTO prices (quantity, price, currency) VALUES (3, 1.2, ?)", (currency,))
            c.execute("INSERT OR IGNORE INTO prices (quantity, price, currency) VALUES (5, 1.8, ?)", (currency,))
    # Insert default payment methods
    c.execute("INSERT OR IGNORE INTO payments (method_name, method_id) VALUES ('Bkash', '017XXXXXXXX')")
    c.execute("INSERT OR IGNORE INTO payments (method_name, method_id) VALUES ('Nagad', '018XXXXXXXX')")
    c.execute("INSERT OR IGNORE INTO payments (method_name, method_id) VALUES ('Rocket', '019XXXXXXXX')")
    conn.commit()
    conn.close()

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect('socks5_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

def add_user(user_id, username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, currency) VALUES (?, ?, ?)", (user_id, username, DEFAULT_CURRENCY))
    conn.commit()
    conn.close()

def get_user_balance(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT balance, currency FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return (result['balance'], result['currency']) if result else (0, DEFAULT_CURRENCY)

def update_user_balance(user_id, amount):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def add_proxies(proxies, country):
    conn = get_db_connection()
    c = conn.cursor()
    for proxy in proxies:
        c.execute("INSERT INTO proxies (ip, port, username, password, country) VALUES (?, ?, ?, ?, ?)",
                  (proxy['ip'], proxy['port'], proxy['username'], proxy['password'], country))
    conn.commit()
    conn.close()

def remove_proxy(ip_port):
    conn = get_db_connection()
    c = conn.cursor()
    ip, port = ip_port.split(':')
    c.execute("DELETE FROM proxies WHERE ip = ? AND port = ?", (ip, port))
    conn.commit()
    conn.close()

def get_available_proxies_count(country=None):
    conn = get_db_connection()
    c = conn.cursor()
    if country:
        c.execute("SELECT COUNT(*) as count FROM proxies WHERE is_sold = FALSE AND country = ?", (country,))
    else:
        c.execute("SELECT COUNT(*) as count FROM proxies WHERE is_sold = FALSE")
    result = c.fetchone()
    conn.close()
    return result['count'] if result else 0

def get_available_countries():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT country FROM proxies WHERE is_sold = FALSE ORDER BY country")
    result = c.fetchall()
    conn.close()
    return [r['country'] for r in result] if result else []

def get_proxies_for_user(user_id, limit=5):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT ip, port, username, password, country FROM proxies WHERE sold_to = ? ORDER BY sold_at DESC LIMIT ?", (user_id, limit))
    result = c.fetchall()
    conn.close()
    return result

def get_proxies_by_country(country, limit=100):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT ip, port, username, password FROM proxies WHERE country = ? AND is_sold = FALSE LIMIT ?", (country, limit))
    result = c.fetchall()
    conn.close()
    return result

def sell_proxies_to_user(user_id, quantity, country=None):
    conn = get_db_connection()
    c = conn.cursor()
    # Get user currency
    c.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,))
    user_currency = c.fetchone()['currency']
    # Get available proxies
    if country:
        c.execute("SELECT id, ip, port, username, password FROM proxies WHERE is_sold = FALSE AND country = ? LIMIT ?", (country, quantity))
    else:
        c.execute("SELECT id, ip, port, username, password FROM proxies WHERE is_sold = FALSE LIMIT ?", (quantity,))
    proxies = c.fetchall()
    if len(proxies) < quantity:
        return None
    # Calculate total price
    c.execute("SELECT price FROM prices WHERE quantity = ? AND currency = ?", (quantity, user_currency))
    price_info = c.fetchone()
    if not price_info:
        return "invalid_quantity"
    total_price = price_info['price']
    # Check user balance
    user_balance, _ = get_user_balance(user_id)
    if user_balance < total_price:
        return "insufficient_balance"
    # Mark proxies as sold
    proxy_ids = [proxy['id'] for proxy in proxies]
    placeholders = ','.join(['?'] * len(proxy_ids))
    c.execute(f"UPDATE proxies SET is_sold = TRUE, sold_to = ?, sold_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
              (user_id, *proxy_ids))
    # Deduct from user balance
    update_user_balance(user_id, -total_price)
    conn.commit()
    conn.close()
    return [dict(proxy) for proxy in proxies]

def get_payment_methods():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT method_name, method_id FROM payments WHERE is_active = TRUE")
    result = c.fetchall()
    conn.close()
    return result

def add_payment_method(method_name, method_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO payments (method_name, method_id) VALUES (?, ?)", (method_name, method_id))
    conn.commit()
    conn.close()

def remove_payment_method(method_name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE payments SET is_active = FALSE WHERE method_name = ?", (method_name,))
    conn.commit()
    conn.close()

def get_prices(currency=None):
    conn = get_db_connection()
    c = conn.cursor()
    if currency:
        c.execute("SELECT quantity, price, currency FROM prices WHERE currency = ? ORDER BY quantity", (currency,))
    else:
        c.execute("SELECT quantity, price, currency FROM prices ORDER BY currency, quantity")
    result = c.fetchall()
    conn.close()
    return result

def set_price(quantity, price, currency):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO prices (quantity, price, currency) VALUES (?, ?, ?)", (quantity, price, currency))
    conn.commit()
    conn.close()

def add_deposit(user_id, amount, method, proof=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO deposits (user_id, amount, method, proof) VALUES (?, ?, ?, ?)", (user_id, amount, method, proof))
    deposit_id = c.lastrowid
    conn.commit()
    conn.close()
    return deposit_id

def get_deposit(deposit_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM deposits WHERE id = ?", (deposit_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_deposit_status(deposit_id, status, admin_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    if admin_id:
        c.execute("UPDATE deposits SET status = ?, admin_action_by = ?, admin_action_at = CURRENT_TIMESTAMP WHERE id = ?", (status, admin_id, deposit_id))
    else:
        c.execute("UPDATE deposits SET status = ? WHERE id = ?", (status, deposit_id))
    conn.commit()
    conn.close()

def get_user_deposits(user_id, limit=10):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, amount, method, proof, status, created_at FROM deposits WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    result = c.fetchall()
    conn.close()
    return result

def get_pending_deposits():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT d.id, d.user_id, d.amount, d.method, d.proof, d.created_at, u.username FROM deposits d JOIN users u ON d.user_id = u.user_id WHERE d.status = 'pending' ORDER BY d.created_at ASC")
    result = c.fetchall()
    conn.close()
    return result

def get_stats():
    conn = get_db_connection()
    c = conn.cursor()
    # Total proxies
    c.execute("SELECT COUNT(*) as count FROM proxies")
    total_proxies = c.fetchone()['count']
    # Total users
    c.execute("SELECT COUNT(*) as count FROM users")
    total_users = c.fetchone()['count']
    # Today's sales
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) as count FROM proxies WHERE DATE(sold_at) = ?", (today,))
    today_sales_result = c.fetchone()
    today_sales = today_sales_result['count'] if today_sales_result else 0
    # Countries count
    c.execute("SELECT country, COUNT(*) as count FROM proxies WHERE is_sold = FALSE GROUP BY country")
    countries = c.fetchall()
    # Pending deposits count
    c.execute("SELECT COUNT(*) as count FROM deposits WHERE status = 'pending'")
    pending_deposits = c.fetchone()['count']
    conn.close()
    return {
        'total_proxies': total_proxies,
        'total_users': total_users,
        'today_sales': today_sales,
        'countries': countries,
        'pending_deposits': pending_deposits
    }

# File parsing utility
def parse_proxy_file(file_content, filename):
    proxies = []
    if filename.endswith('.txt'):
        lines = file_content.split('\n')
        for line in lines:
            line = line.strip()
            if re.match(r'^\d+\.\d+\.\d+\.\d+:\d+:.+:.+$', line):
                parts = line.split(':')
                proxies.append({
                    'ip': parts[0],
                    'port': int(parts[1]),
                    'username': parts[2],
                    'password': parts[3]
                })
    elif filename.endswith('.csv'):
        lines = file_content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(',')
                if len(parts) >= 4:
                    proxies.append({
                        'ip': parts[0],
                        'port': int(parts[1]),
                        'username': parts[2],
                        'password': parts[3]
                    })
    elif filename.endswith('.html'):
        # Simple HTML parsing - look for table rows
        rows = re.findall(r'<tr>(.*?)</tr>', file_content, re.DOTALL)
        for row in rows:
            cells = re.findall(r'<td>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 4:
                proxies.append({
                    'ip': cells[0],
                    'port': int(cells[1]),
                    'username': cells[2],
                    'password': cells[3]
                })
    return proxies

# Notification functions
def notify_admins(context, message):
    for admin_id in ADMIN_IDS:
        try:
            context.bot.send_message(chat_id=admin_id, text=message)
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

def notify_user(context, user_id, message):
    try:
        context.bot.send_message(chat_id=user_id, text=message)
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

# Bot command handlers
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user(user.id, user.username)
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='user_balance')],
        [InlineKeyboardButton("💵 Deposit", callback_data='user_deposit')],
        [InlineKeyboardButton("🛒 Buy (SOCKS5)", callback_data='user_buy_proxy')],
        [InlineKeyboardButton("🔒 My Proxies", callback_data='user_my_proxies')],
        [InlineKeyboardButton("📜 My Deposits", callback_data='user_my_deposits')],
        [InlineKeyboardButton("ℹ️ Prices", callback_data='user_prices')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "👋 Welcome! You are in SOCKS5 Proxy Bot.\n\n"
        "📌 Choose any option from the buttons below or use text commands.",
        reply_markup=reply_markup
    )

def help_command(update: Update, context: CallbackContext):
    help_text = (
        "📖 Available Commands:\n\n"
        "/start - Show main menu with inline buttons\n"
        "/help - Show this help message\n"
        "/prices - Show price list\n"
        "/stock - Check available proxy stock\n"
        "/buy [number] - Buy proxies (e.g., /buy 3)\n"
        "/myproxies - List your active proxies\n"
        "/export_myproxies - Export your proxies as .txt file\n"
        "/balance - Check your balance\n"
        "/deposit - Show deposit instructions\n"
        "/mydeposits - Show your last 10 deposits\n"
        "/cancel - Cancel current operation\n\n"
        "For admins:\n"
        "/admin - Show admin panel\n"
        "/addproxy - Upload proxy file\n"
        "/removeproxy [IP:PORT] - Remove specific proxy\n"
        "/setpayment [method] [id] - Add payment method\n"
        "/removepayment [method] - Remove payment method\n"
        "/setprice [qty] [price] [currency] - Set price\n"
    )
    update.message.reply_text(help_text)

def prices(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    _, user_currency = get_user_balance(user_id)
    prices = get_prices(user_currency)
    price_list = "\n".join([f"{p['quantity']} proxy - {p['price']} {p['currency']}" for p in prices])
    update.message.reply_text(f"🏷️ Price List ({user_currency}):\n{price_list}")

def stock(update: Update, context: CallbackContext):
    count = get_available_proxies_count()
    countries = get_available_countries()
    if countries:
        country_stats = "\n".join([f"{country}: {get_available_proxies_count(country)}" for country in countries])
        update.message.reply_text(f"📦 Available proxies in stock: {count}\n\nBy country:\n{country_stats}")
    else:
        update.message.reply_text(f"📦 Available proxies in stock: {count}")

def buy(update: Update, context: CallbackContext):
    if not context.args:  # Show country selection for buying
        countries = get_available_countries()
        if not countries:
            update.message.reply_text("❌ No proxies available in stock.")
            return
        keyboard = []
        for country in countries:
            count = get_available_proxies_count(country)
            keyboard.append([InlineKeyboardButton(f"{country} ({count} available)", callback_data=f'buy_{country}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("🌍 Select country for proxies:", reply_markup=reply_markup)
        return
    try:
        quantity = int(context.args[0])
        user_id = update.effective_user.id
        country = context.user_data.get('buy_country') if 'buy_country' in context.user_data else None
        result = sell_proxies_to_user(user_id, quantity, country)
        if result == "insufficient_balance":
            update.message.reply_text("❌ Insufficient balance. Please deposit first.")
        elif result == "invalid_quantity":
            update.message.reply_text("❌ Invalid quantity. You can only buy predefined quantities (e.g., 1, 3, 5).")
        elif not result:
            update.message.reply_text("❌ Not enough proxies in stock.")
        else:
            proxies_text = "\n".join([
                f"{p['ip']}:{p['port']}:{p['username']}:{p['password']}"
                for p in result
            ])
            update.message.reply_text(
                f"✅ Successfully purchased {quantity} proxies:\n\n"
                f"{proxies_text}\n\n"
                "You can use /myproxies to view them anytime."
            )
            if 'buy_country' in context.user_data:
                del context.user_data['buy_country']
    except ValueError:
        update.message.reply_text("Please provide a valid number. Example: /buy 3")

def myproxies(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    proxies = get_proxies_for_user(user_id)
    if not proxies:
        update.message.reply_text("You don't have any proxies yet.")
        return
    proxies_list = "\n".join([
        f"{p['ip']}:{p['port']}:{p['username']}:{p['password']} ({p['country']})"
        for p in proxies
    ])
    update.message.reply_text(f"🔐 Your active proxies:\n{proxies_list}")

def export_myproxies(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    proxies = get_proxies_for_user(user_id, limit=100)  # Increased limit for export
    if not proxies:
        update.message.reply_text("You don't have any proxies to export.")
        return
    proxies_text = "\n".join([
        f"{p['ip']}:{p['port']}:{p['username']}:{p['password']}"
        for p in proxies
    ])
    context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=proxies_text.encode('utf-8'),
        filename="my_proxies.txt"
    )

def balance(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    balance, currency = get_user_balance(user_id)
    update.message.reply_text(f"✅ Your balance: {balance} {currency}")

def deposit(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if 'deposit_process' in context.user_data:
        update.message.reply_text("❌ You already have a deposit in process. Please complete it or use /cancel.")
        return
    payment_methods = get_payment_methods()
    if not payment_methods:
        update.message.reply_text("No payment methods available. Please contact admin.")
        return
    methods_text = "\n".join([f"{p['method_name']}: {p['method_id']}" for p in payment_methods])
    update.message.reply_text(
        f"📥 Deposit instructions:\n\n{methods_text}\n\n"
        "Please send the amount you want to deposit followed by the payment method.\n"
        "Example: `500 Bkash`\n\n"
        "After sending money, please provide the transaction ID or proof."
    )
    context.user_data['deposit_process'] = 'waiting_amount_method'

def handle_deposit_amount(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if 'deposit_process' not in context.user_data or context.user_data['deposit_process'] != 'waiting_amount_method':
        return
    try:
        text = update.message.text
        parts = text.split()
        if len(parts) < 2:
            update.message.reply_text("❌ Please provide both amount and payment method. Example: `500 Bkash`")
            return
        amount = float(parts[0])
        method = ' '.join(parts[1:])
        payment_methods = get_payment_methods()
        valid_methods = [p['method_name'] for p in payment_methods]
        if method not in valid_methods:
            update.message.reply_text(f"❌ Invalid payment method. Available methods: {', '.join(valid_methods)}")
            return
        context.user_data['deposit_amount'] = amount
        context.user_data['deposit_method'] = method
        context.user_data['deposit_process'] = 'waiting_proof'
        update.message.reply_text(
            f"✅ Amount: {amount} {DEFAULT_CURRENCY}\n"
            f"✅ Method: {method}\n\n"
            "Please send your transaction ID or proof (screenshot)."
        )
    except ValueError:
        update.message.reply_text("❌ Please provide a valid amount. Example: `500 Bkash`")

def handle_deposit_proof(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if 'deposit_process' not in context.user_data or context.user_data['deposit_process'] != 'waiting_proof':
        return
    if 'deposit_amount' not in context.user_data or 'deposit_method' not in context.user_data:
        update.message.reply_text("❌ Deposit process error. Please start over with /deposit")
        context.user_data.pop('deposit_process', None)
        return
    amount = context.user_data['deposit_amount']
    method = context.user_data['deposit_method']
    proof = None
    if update.message.text:
        proof = update.message.text
    elif update.message.photo:
        photo = update.message.photo[-1]
        proof = photo.file_id
    if not proof:
        update.message.reply_text("❌ Please provide a valid transaction ID or proof screenshot.")
        return
    deposit_id = add_deposit(user_id, amount, method, proof)
    user = update.effective_user
    username = f"@{user.username}" if user.username else f"User #{user.id}"
    if isinstance(proof, str) and not proof.startswith('AgAC'):
        admin_message = (
            f"🆕 New Deposit Request #{deposit_id}\n\n"
            f"👤 User: {username} ({user.id})\n"
            f"💰 Amount: {amount} {DEFAULT_CURRENCY}\n"
            f"💳 Method: {method}\n"
            f"📋 Proof: {proof}\n\n"
            "Use buttons below to approve or reject:"
        )
    else:
        admin_message = (
            f"🆕 New Deposit Request #{deposit_id}\n\n"
            f"👤 User: {username} ({user.id})\n"
            f"💰 Amount: {amount} {DEFAULT_CURRENCY}\n"
            f"💳 Method: {method}\n"
            f"📋 Proof: [Photo attached]\n\n"
            "Use buttons below to approve or reject:"
        )
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_deposit_{deposit_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_deposit_{deposit_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    for admin_id in ADMIN_IDS:
        try:
            if isinstance(proof, str) and not proof.startswith('AgAC'):
                context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    reply_markup=reply_markup
                )
            else:
                context.bot.send_photo(
                    chat_id=admin_id,
                    photo=proof,
                    caption=admin_message,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    update.message.reply_text(
        f"✅ Your deposit request for {amount} {DEFAULT_CURRENCY} via {method} has been submitted.\n"
        "Please wait for admin approval. You will be notified once processed."
    )
    context.user_data.pop('deposit_process', None)
    context.user_data.pop('deposit_amount', None)
    context.user_data.pop('deposit_method', None)

def mydeposits(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    deposits = get_user_deposits(user_id)
    if not deposits:
        update.message.reply_text("You don't have any deposits yet.")
        return
    deposits_list = []
    for deposit in deposits:
        status_icon = "✅" if deposit['status'] == 'approved' else "❌" if deposit['status'] == 'rejected' else "⏳"
        deposits_list.append(
            f"{status_icon} {deposit['amount']} {DEFAULT_CURRENCY} via {deposit['method']} - {deposit['status']} ({deposit['created_at']})"
        )
    update.message.reply_text(f"📌 Your deposits:\n" + "\n".join(deposits_list))

def cancel(update: Update, context: CallbackContext):
    if 'deposit_process' in context.user_data:
        context.user_data.pop('deposit_process', None)
        context.user_data.pop('deposit_amount', None)
        context.user_data.pop('deposit_method', None)
    if 'expecting_country' in context.user_data:
        context.user_data.pop('expecting_country', None)
    if 'proxy_country' in context.user_data:
        context.user_data.pop('proxy_country', None)
    if 'buy_country' in context.user_data:
        context.user_data.pop('buy_country', None)
    update.message.reply_text("✅ Current operation cancelled.")

# Admin commands
def admin_panel(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ This operation is for admins only!")
        return
    stats = get_stats()
    keyboard = [
        [InlineKeyboardButton("➕ Add Proxy", callback_data='admin_add_proxy')],
        [InlineKeyboardButton("➖ Remove Proxy", callback_data='admin_remove_proxy')],
        [InlineKeyboardButton("💳 Set Payment Method", callback_data='admin_set_payment')],
        [InlineKeyboardButton("🗑 Remove Payment Method", callback_data='admin_remove_payment')],
        [InlineKeyboardButton("🏷 Set Price", callback_data='admin_set_price')],
        [InlineKeyboardButton("📊 View Stats", callback_data='admin_view_stats')],
        [InlineKeyboardButton("📋 Pending Deposits", callback_data='admin_pending_deposits')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"🔐 ADMIN PANEL\n\n"
        f"📊 Stats:\n"
        f"• Users: {stats['total_users']}\n"
        f"• Proxies: {stats['total_proxies']}\n"
        f"• Today's Sales: {stats['today_sales']}\n"
        f"• Pending Deposits: {stats['pending_deposits']}\n\n"
        "Choose from options below:",
        reply_markup=reply_markup
    )

def add_proxy(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ This operation is for admins only!")
        return
    update.message.reply_text("🌍 Please enter the country name for these proxies:")
    context.user_data['expecting_country'] = True

def remove_proxy(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ This operation is for admins only!")
        return
    countries = get_available_countries()
    if not countries:
        update.message.reply_text("❌ No proxies available to remove.")
        return
    keyboard = []
    for country in countries:
        count = get_available_proxies_count(country)
        keyboard.append([InlineKeyboardButton(f"{country} ({count} proxies)", callback_data=f'remove_{country}')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🌍 Select country to remove proxies from:", reply_markup=reply_markup)

def set_payment(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ This operation is for admins only!")
        return
    if len(context.args) < 2:
        update.message.reply_text(
            "❌ Please provide payment method name and ID\n\n"
            "Format: [name] [id]\n"
            "Example: /setpayment Bkash 017XXXXXXXX"
        )
        return
    method_name = context.args[0]
    method_id = ' '.join(context.args[1:])
    add_payment_method(method_name, method_id)
    update.message.reply_text(f"✅ Added payment method: {method_name} - {method_id}")

def remove_payment(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ This operation is for admins only!")
        return
    if not context.args:
        update.message.reply_text(
            "❌ Please provide payment method name to remove\n\n"
            "Example: /removepayment Bkash"
        )
        return
    method_name = context.args[0]
    remove_payment_method(method_name)
    update.message.reply_text(f"✅ Removed payment method: {method_name}")

def set_price(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ This operation is for admins only!")
        return
    if len(context.args) < 3:
        update.message.reply_text(
            "❌ Please provide quantity, price, and currency\n\n"
            "Format: [quantity] [price] [currency]\n"
            "Example: /setprice 1 50 BDT\n"
            f"Supported currencies: {', '.join(SUPPORTED_CURRENCIES)}"
        )
        return
    try:
        quantity = int(context.args[0])
        price = float(context.args[1])
        currency = context.args[2].upper()
        if currency not in SUPPORTED_CURRENCIES:
            update.message.reply_text(f"❌ Unsupported currency. Supported: {', '.join(SUPPORTED_CURRENCIES)}")
            return
        set_price(quantity, price, currency)
        update.message.reply_text(f"✅ Set price for {quantity} proxies: {price} {currency}")
    except ValueError:
        update.message.reply_text("❌ Please provide valid numbers for quantity and price")

# File upload handler
def handle_file_upload(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if 'expecting_country' in context.user_data and context.user_data['expecting_country']:
        country = update.message.text
        context.user_data['proxy_country'] = country
        context.user_data['expecting_country'] = False
        update.message.reply_text(f"🌍 Country set to: {country}. Now please upload the proxy file.")
        return
    if 'proxy_country' not in context.user_data:
        update.message.reply_text("❌ Please set country first using /addproxy")
        return
    document = update.message.document
    if not document:
        return
    file = context.bot.get_file(document.file_id)
    filename = document.file_name
    country = context.user_data['proxy_country']
    if not (filename.endswith('.txt') or filename.endswith('.csv') or filename.endswith('.html')):
        update.message.reply_text("❌ Unsupported file format. Please upload .txt, .csv, or .html files.")
        return
    file_content = file.download_as_bytearray().decode('utf-8')
    proxies = parse_proxy_file(file_content, filename)
    if not proxies:
        update.message.reply_text("❌ No valid proxies found in the file.")
        return
    add_proxies(proxies, country)
    update.message.reply_text(f"✅ Added {len(proxies)} {country} proxies from {filename}")
    del context.user_data['proxy_country']

# Button callback handler
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == 'user_balance':
        balance, currency = get_user_balance(user_id)
        query.edit_message_text(text=f"✅ Your balance: {balance} {currency}")
    elif data == 'user_deposit':
        if 'deposit_process' in context.user_data:
            query.edit_message_text(text="❌ You already have a deposit in process. Please complete it or use /cancel.")
            return
        payment_methods = get_payment_methods()
        if not payment_methods:
            query.edit_message_text(text="No payment methods available. Please contact admin.")
            return
        methods_text = "\n".join([f"{p['method_name']}: {p['method_id']}" for p in payment_methods])
        query.edit_message_text(
            text=f"📥 Deposit instructions:\n\n{methods_text}\n\n"
                 "Please send the amount you want to deposit followed by the payment method.\n"
                 "Example: `500 Bkash`\n\n"
                 "After sending money, please provide the transaction ID or proof."
        )
        context.user_data['deposit_process'] = 'waiting_amount_method'
    elif data == 'user_buy_proxy':
        countries = get_available_countries()
        if not countries:
            query.edit_message_text(text="❌ No proxies available in stock.")
            return
        keyboard = []
        for country in countries:
            count = get_available_proxies_count(country)
            keyboard.append([InlineKeyboardButton(f"{country} ({count} available)", callback_data=f'buy_{country}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="🌍 Select country for proxies:", reply_markup=reply_markup)
    elif data.startswith('buy_'):
        country = data[4:]
        context.user_data['buy_country'] = country
        query.edit_message_text(text=f"🌍 Selected: {country}. How many proxies do you want to buy? (1, 3, 5...)\n\nExample: /buy 3")
    elif data == 'user_my_proxies':
        proxies = get_proxies_for_user(user_id)
        if not proxies:
            query.edit_message_text(text="You don't have any proxies yet.")
            return
        proxies_list = "\n".join([
            f"{p['ip']}:{p['port']}:{p['username']}:{p['password']} ({p['country']})"
            for p in proxies
        ])
        query.edit_message_text(text=f"🔐 Your active proxies:\n{proxies_list}")
    elif data == 'user_my_deposits':
        deposits = get_user_deposits(user_id)
        if not deposits:
            query.edit_message_text(text="You don't have any deposits yet.")
            return
        deposits_list = []
        for deposit in deposits:
            status_icon = "✅" if deposit['status'] == 'approved' else "❌" if deposit['status'] == 'rejected' else "⏳"
            deposits_list.append(
                f"{status_icon} {deposit['amount']} {DEFAULT_CURRENCY} via {deposit['method']} - {deposit['status']} ({deposit['created_at']})"
            )
        query.edit_message_text(text=f"📌 Your deposits:\n" + "\n".join(deposits_list))
    elif data == 'user_prices':
        user_id = query.from_user.id
        _, user_currency = get_user_balance(user_id)
        prices = get_prices(user_currency)
        price_list = "\n".join([f"{p['quantity']} proxy - {p['price']} {p['currency']}" for p in prices])
        query.edit_message_text(text=f"🏷️ Price List ({user_currency}):\n{price_list}")
    # Admin buttons
    elif data == 'admin_add_proxy':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        query.edit_message_text(text="🌍 Please enter the country name for these proxies:")
        context.user_data['expecting_country'] = True
    elif data == 'admin_remove_proxy':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        countries = get_available_countries()
        if not countries:
            query.edit_message_text(text="❌ No proxies available to remove.")
            return
        keyboard = []
        for country in countries:
            count = get_available_proxies_count(country)
            keyboard.append([InlineKeyboardButton(f"{country} ({count} proxies)", callback_data=f'remove_{country}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="🌍 Select country to remove proxies from:", reply_markup=reply_markup)
    elif data.startswith('remove_'):
        country = data[7:]
        proxies = get_proxies_by_country(country)
        if not proxies:
            query.edit_message_text(text=f"❌ No proxies found for {country}.")
            return
        proxies_list = "\n".join([f"{p['ip']}:{p['port']}" for p in proxies[:10]])
        if len(proxies) > 10:
            proxies_list += f"\n... and {len(proxies) - 10} more"
        query.edit_message_text(
            text=f"❌ Proxies for {country}:\n{proxies_list}\n\n"
                 "To remove, use: /removeproxy IP:PORT\n"
                 "Example: /removeproxy 192.168.0.1:1080"
        )
    elif data == 'admin_set_payment':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        query.edit_message_text(text="💳 Add new payment method:\n\nFormat: [name] [id]\nExample: Bkash 017XXXXXXXX")
    elif data == 'admin_remove_payment':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        query.edit_message_text(text="🗑️ Enter payment method name to remove:\n\nExample: Bkash")
    elif data == 'admin_set_price':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        query.edit_message_text(
            text="🏷️ Set new proxy price:\n\n"
                 "Format: [quantity] [price] [currency]\n"
                 "Example: 1 50 BDT\n"
                 f"Supported currencies: {', '.join(SUPPORTED_CURRENCIES)}"
        )
    elif data == 'admin_view_stats':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        stats = get_stats()
        countries_text = "\n".join([f"{c['country']}: {c['count']}" for c in stats['countries']]) if stats['countries'] else "None"
        query.edit_message_text(
            text=f"📊 Statistics:\n"
                 f"Total proxies: {stats['total_proxies']}\n"
                 f"Total users: {stats['total_users']}\n"
                 f"Today's sales: {stats['today_sales']}\n"
                 f"Pending deposits: {stats['pending_deposits']}\n\n"
                 f"By country:\n{countries_text}"
        )
    elif data == 'admin_pending_deposits':
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        deposits = get_pending_deposits()
        if not deposits:
            query.edit_message_text(text="✅ No pending deposits.")
            return
        deposits_text = ""
        for deposit in deposits[:5]:
            deposits_text += (
                f"🆔 #{deposit['id']}\n"
                f"👤 {deposit['username']} ({deposit['user_id']})\n"
                f"💰 {deposit['amount']} {DEFAULT_CURRENCY} via {deposit['method']}\n"
                f"⏰ {deposit['created_at']}\n\n"
            )
        if len(deposits) > 5:
            deposits_text += f"... and {len(deposits) - 5} more pending deposits\n\n"
        deposits_text += "Use /admin to manage deposits."
        query.edit_message_text(text=deposits_text)
    elif data.startswith('approve_deposit_'):
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        deposit_id = int(data.split('_')[-1])
        deposit = get_deposit(deposit_id)
        if not deposit:
            query.edit_message_text(text="❌ Deposit not found.")
            return
        if deposit['status'] != 'pending':
            query.edit_message_text(text=f"❌ Deposit already {deposit['status']}.")
            return
        update_deposit_status(deposit_id, 'approved', user_id)
        update_user_balance(deposit['user_id'], deposit['amount'])
        notify_user(
            context,
            deposit['user_id'],
            f"✅ Your deposit of {deposit['amount']} {DEFAULT_CURRENCY} has been approved!\n"
            f"Your new balance: {get_user_balance(deposit['user_id'])[0]} {DEFAULT_CURRENCY}"
        )
        query.edit_message_text(
            text=f"✅ Deposit #{deposit_id} approved by admin.\n"
                 f"User: {deposit['user_id']}\n"
                 f"Amount: {deposit['amount']} {DEFAULT_CURRENCY}"
        )
    elif data.startswith('reject_deposit_'):
        if user_id not in ADMIN_IDS:
            query.edit_message_text(text="⛔ This operation is for admins only!")
            return
        deposit_id = int(data.split('_')[-1])
        deposit = get_deposit(deposit_id)
        if not deposit:
            query.edit_message_text(text="❌ Deposit not found.")
            return
        if deposit['status'] != 'pending':
            query.edit_message_text(text=f"❌ Deposit already {deposit['status']}.")
            return
        update_deposit_status(deposit_id, 'rejected', user_id)
        notify_user(
            context,
            deposit['user_id'],
            f"❌ Your deposit of {deposit['amount']} {DEFAULT_CURRENCY} was rejected.\n"
            "Please contact admin for more information."
        )
        query.edit_message_text(
            text=f"❌ Deposit #{deposit_id} rejected by admin.\n"
                 f"User: {deposit['user_id']}\n"
                 f"Amount: {deposit['amount']} {DEFAULT_CURRENCY}"
        )

# Message handler for country input
def handle_country_input(update: Update, context: CallbackContext):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if 'expecting_country' in context.user_data and context.user_data['expecting_country']:
        country = update.message.text
        context.user_data['proxy_country'] = country
        context.user_data['expecting_country'] = False
        update.message.reply_text(f"🌍 Country set to: {country}. Now please upload the proxy file.")

# Message handler for deposit amount
def handle_message(update: Update, context: CallbackContext):
    # Check if user is in deposit process
    if 'deposit_process' in context.user_data:
        if context.user_data['deposit_process'] == 'waiting_amount_method':
            handle_deposit_amount(update, context)
        elif context.user_data['deposit_process'] == 'waiting_proof':
            handle_deposit_proof(update, context)
        return
    # Check if admin is setting country
    handle_country_input(update, context)

def main():
    init_db()
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("prices", prices))
    dp.add_handler(CommandHandler("stock", stock))
    dp.add_handler(CommandHandler("buy", buy))
    dp.add_handler(CommandHandler("myproxies", myproxies))
    dp.add_handler(CommandHandler("export_myproxies", export_myproxies))
    dp.add_handler(CommandHandler("balance", balance))
    dp.add_handler(CommandHandler("deposit", deposit))
    dp.add_handler(CommandHandler("mydeposits", mydeposits))
    dp.add_handler(CommandHandler("cancel", cancel))
    dp.add_handler(CommandHandler("admin", admin_panel))
    dp.add_handler(CommandHandler("addproxy", add_proxy))
    dp.add_handler(CommandHandler("removeproxy", remove_proxy))
    dp.add_handler(CommandHandler("setpayment", set_payment))
    dp.add_handler(CommandHandler("removepayment", remove_payment))
    dp.add_handler(CommandHandler("setprice", set_price))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    dp.add_handler(MessageHandler(filters.PHOTO, handle_message))
    updater.start_polling()
    logger.info("Bot started successfully!")
    updater.idle()

if __name__ == '__main__':
    main()
