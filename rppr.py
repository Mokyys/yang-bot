import telebot
from telebot import types
import sqlite3
import random
import time
from datetime import datetime, timedelta
import threading

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "BOT_TOKEN"  # Получите у @BotFather
ADMIN_IDS = [7340922523, 5495313697]  # Ваши ID для админки
bot = telebot.TeleBot(TOKEN)

# ==================== БАЗА ДАННЫХ ====================
def get_connection():
    """Создает новое соединение с БД для каждого потока"""
    return sqlite3.connect('yangs.db', check_same_thread=False)

def init_database():
    """Создание всех таблиц при запуске"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_join BOOLEAN DEFAULT 1,
        last_bonus TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица проектов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        project_name TEXT UNIQUE,
        balance REAL DEFAULT 100000.0,
        players INTEGER DEFAULT 0,
        hosting TEXT DEFAULT 'Средний',
        rating REAL DEFAULT 0.0,
        ads INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        vip INTEGER DEFAULT 0,
        ad_counter INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица промокодов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        amount REAL,
        creator_id INTEGER DEFAULT NULL,
        used_by INTEGER DEFAULT NULL,
        used_at TIMESTAMP DEFAULT NULL,
        is_special BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица доната
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS donations (
        donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_name TEXT,
        price REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица атак
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attacks (
        attack_id INTEGER PRIMARY KEY AUTOINCREMENT,
        attacker_id INTEGER,
        target_name TEXT,
        damage REAL,
        success BOOLEAN,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана")

init_database()

# Создаем промокод YANGTRAPPA
def create_yang_promo():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO promocodes (code, amount, is_special) VALUES (?, ?, 1)', 
                  ('YANGTRAPPA', 350000))
    conn.commit()
    conn.close()
    print("✅ Промокод YANGTRAPPA создан (350,000$)")

create_yang_promo()
# ==================== ФУНКЦИИ БАЗЫ ДАННЫХ ====================
def create_project(user_id, username, project_name):
    """Создание нового проекта"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем уникальность
        cursor.execute('SELECT * FROM projects WHERE project_name = ?', (project_name,))
        if cursor.fetchone():
            return False, "❌ Проект с таким названием уже существует!"
        
        # Проверяем есть ли у пользователя проект
        cursor.execute('SELECT * FROM projects WHERE user_id = ?', (user_id,))
        if cursor.fetchone():
            return False, "❌ У вас уже есть проект!"
        
        # Добавляем пользователя
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                      (user_id, username))
        
        # Создаем проект
        cursor.execute('''
        INSERT INTO projects (user_id, project_name, username) 
        VALUES (?, ?, ?)
        ''', (user_id, project_name, username))
        
        conn.commit()
        
        # Проверяем новый ли пользователь
        cursor.execute('SELECT first_join FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user and user[0] == 1:
            message = f"""🎉 Проект '{project_name}' создан!
💰 Баланс: 100,000$

🎁 **НОВЫЙ ПОЛЬЗОВАТЕЛЬ!**
Получите промокод: `YANGTRAPPA`
Активируйте: /promo YANGTRAPPA
Награда: **350,000$** 💰"""
            cursor.execute('UPDATE users SET first_join = 0 WHERE user_id = ?', (user_id,))
            conn.commit()
        else:
            message = f"🎉 Проект '{project_name}' создан!\n💰 Баланс: 100,000$"
        
        return True, message
    finally:
        conn.close()

def get_project(user_id=None, project_name=None):
    """Получение проекта"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if user_id:
            cursor.execute('SELECT * FROM projects WHERE user_id = ?', (user_id,))
        elif project_name:
            cursor.execute('SELECT * FROM projects WHERE project_name = ?', (project_name,))
        
        result = cursor.fetchone()
        if result:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, result))
        return None
    finally:
        conn.close()

def update_balance(user_id, amount, description="", trans_type="other"):
    """Обновление баланса"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE projects SET balance = balance + ? WHERE user_id = ?', 
                      (amount, user_id))
        conn.commit()
    finally:
        conn.close()

def calculate_ad_price(user_id, ad_count):
    """Расчет цены рекламы (10,000$ + 500$ за каждую следующую)"""
    base_price = 10000
    price_increase = 500
    
    # Цена = 10,000$ + (номер_рекламы - 1) * 500$
    total_price = base_price + (ad_count * price_increase)
    return total_price

def buy_ad(user_id, ad_count=1, use_all=False):
    """Покупка рекламы с прогрессивной ценой"""
    project = get_project(user_id=user_id)
    if not project:
        return False, "❌ Проект не найден"
    
    balance = project['balance']
    current_ad_count = project['ad_counter']
    
    if use_all:
        # Рассчитываем сколько реклам можно купить
        affordable_ads = 0
        total_price = 0
        
        while True:
            next_ad_price = calculate_ad_price(user_id, current_ad_count + affordable_ads)
            if total_price + next_ad_price <= balance:
                affordable_ads += 1
                total_price += next_ad_price
            else:
                break
        
        ad_count = affordable_ads
        if ad_count == 0:
            return False, "❌ Недостаточно средств даже для 1 рекламы"
    else:
        # Рассчитываем цену для указанного количества
        total_price = 0
        for i in range(ad_count):
            total_price += calculate_ad_price(user_id, current_ad_count + i)
        
        if balance < total_price:
            return False, f"❌ Недостаточно средств. Нужно: ${total_price:,.0f}"
    
    # Списание и обновление
    update_balance(user_id, -total_price)
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Обновляем счетчик реклам и рейтинг
        cursor.execute('''
        UPDATE projects SET 
            ads = ads + ?,
            rating = rating + ?,
            ad_counter = ad_counter + ? 
        WHERE user_id = ?
        ''', (ad_count, ad_count * 0.5, ad_count, user_id))
        
        conn.commit()
    finally:
        conn.close()
    
    # Формируем сообщение о ценах
    price_details = []
    for i in range(ad_count):
        price = calculate_ad_price(user_id, current_ad_count + i)
        price_details.append(f"Реклама #{current_ad_count + i + 1}: ${price:,.0f}")
    
    price_info = "\n".join(price_details[-3:])  # Показываем последние 3 цены
    
    return True, f"""✅ Куплено {ad_count} рекламы за ${total_price:,.0f}
+{ad_count * 0.5}⭐ рейтинга

{price_info if ad_count <= 3 else f'...\n{price_details[-1]}'}"""

def buy_players(user_id, package):
    """Покупка игроков"""
    packages = {
        '100': (100, 300000),
        '250': (250, 540000),
        '300': (300, 600000)
    }
    
    if package not in packages:
        return False, "❌ Неверный пакет"
    
    players, price = packages[package]
    project = get_project(user_id=user_id)
    
    if project['balance'] < price:
        return False, f"❌ Недостаточно средств. Нужно: ${price:,.0f}"
    
    update_balance(user_id, -price)
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE projects SET players = players + ? WHERE user_id = ?',
                      (players, user_id))
        conn.commit()
    finally:
        conn.close()
    
    return True, f"✅ Куплено {players} игроков за ${price:,.0f}"

def upgrade_hosting(user_id):
    """Улучшение хостинга"""
    project = get_project(user_id=user_id)
    
    if project['hosting'] == 'Отличный':
        return False, "❌ Хостинг уже максимального уровня"
    
    if project['balance'] < 500000:
        return False, f"❌ Недостаточно средств. Нужно: $500,000"
    
    update_balance(user_id, -500000)
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE projects SET hosting = ? WHERE user_id = ?',
                      ('Отличный', user_id))
        conn.commit()
    finally:
        conn.close()
    
    return True, "✅ Хостинг улучшен до 'Отличный'!"

# ==================== ЕЖЕДНЕВНЫЙ БОНУС (каждые 3 часа) ====================
def daily_bonus(user_id):
    """Выдача бонуса каждые 3 часа"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            last_bonus = datetime.fromisoformat(result[0])
            time_diff = datetime.now() - last_bonus
            
            if time_diff < timedelta(hours=3):
                hours_left = 3 - time_diff.seconds // 3600
                minutes_left = 59 - (time_diff.seconds // 60) % 60
                return False, f"⏳ Следующий бонус через {hours_left}ч {minutes_left}м"
        
        # Выдаем бонус
        bonus_amount = random.randint(15000, 75000)  # 15-75к
        update_balance(user_id, bonus_amount, "Бонус раз в 3 часа", "bonus")
        
        # Обновляем время
        cursor.execute('UPDATE users SET last_bonus = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        conn.commit()
        
        return True, f"🎁 Бонус получен: **${bonus_amount:,.0f}**\nСледующий через 3 часа!"
    finally:
        conn.close()
        # ==================== DDoS АТАКИ ====================
def ddos_attack(attacker_id, target_name):
    """DDoS атака на проект"""
    attacker = get_project(user_id=attacker_id)
    target = get_project(project_name=target_name)
    
    if not attacker:
        return False, "❌ У вас нет проекта!"
    
    if not target:
        return False, "❌ Целевой проект не найден"
    
    if attacker_id == target['user_id']:
        return False, "❌ Нельзя атаковать свой же проект"
    
    # Проверяем кулдаун (30 минут)
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM attacks WHERE attacker_id = ? ORDER BY created_at DESC LIMIT 1', 
                      (attacker_id,))
        last_attack = cursor.fetchone()
        
        if last_attack:
            columns = [description[0] for description in cursor.description]
            last_attack = dict(zip(columns, last_attack))
            last_time = datetime.fromisoformat(last_attack['created_at'])
            if datetime.now() - last_time < timedelta(minutes=30):
                wait_time = 30 - int((datetime.now() - last_time).seconds / 60)
                return False, f"⏳ Следующая атака через {wait_time} минут"
        
        # Шанс успеха
        success = random.random() < 0.7
        
        if success:
            # Наносим урон (5-15% от баланса)
            damage_percent = random.uniform(0.05, 0.15)
            damage = target['balance'] * damage_percent
            
            # Отнимаем у цели
            cursor.execute('UPDATE projects SET balance = balance - ? WHERE user_id = ?',
                          (damage, target['user_id']))
            
            # Награда атакующему (30%)
            reward = damage * 0.3
            cursor.execute('UPDATE projects SET balance = balance + ? WHERE user_id = ?',
                          (reward, attacker_id))
            
            # Записываем атаку
            cursor.execute('INSERT INTO attacks (attacker_id, target_name, damage, success) VALUES (?, ?, ?, 1)',
                          (attacker_id, target_name, damage))
            
            message = f"✅ Атака успешна!\nУрон: ${damage:,.0f}\nНаграда: ${reward:,.0f}"
        else:
            # Штраф
            penalty = random.randint(10000, 50000)
            cursor.execute('UPDATE projects SET balance = balance - ? WHERE user_id = ?',
                          (penalty, attacker_id))
            
            cursor.execute('INSERT INTO attacks (attacker_id, target_name, damage, success) VALUES (?, ?, ?, 0)',
                          (attacker_id, target_name, penalty))
            
            message = f"❌ Атака отражена!\nШтраф: ${penalty:,.0f}"
        
        conn.commit()
        return True, message
    finally:
        conn.close()

# ==================== ПРОМОКОДЫ ====================
def use_promocode(user_id, code):
    """Активация промокода"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM promocodes WHERE code = ? AND used_by IS NULL', (code,))
        promo = cursor.fetchone()
        
        if not promo:
            return False, "❌ Промокод не найден или уже использован"
        
        columns = [description[0] for description in cursor.description]
        promo = dict(zip(columns, promo))
        
        # Проверяем проект пользователя
        project = get_project(user_id=user_id)
        if not project:
            return False, "❌ Сначала создайте проект!"
        
        # Помечаем как использованный
        cursor.execute('UPDATE promocodes SET used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?',
                      (user_id, code))
        
        # Даем деньги
        update_balance(user_id, promo['amount'], f"Промокод {code}", "promo")
        
        conn.commit()
        return True, f"✅ Промокод активирован! Получено: ${promo['amount']:,.0f}"
    finally:
        conn.close()

# ==================== ТОП ПРОЕКТОВ ====================
def get_top_projects(limit=10):
    """Получение топ проектов"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT project_name, balance, players, rating, hosting, ads FROM projects ORDER BY balance DESC LIMIT ?', (limit,))
        results = cursor.fetchall()
        
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in results]
    finally:
        conn.close()

# ==================== АДМИН ФУНКЦИИ ====================
def admin_give_all_money(amount):
    """Выдать всем деньги"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE projects SET balance = balance + ?', (amount,))
        affected = cursor.rowcount
        conn.commit()
        return affected
    finally:
        conn.close()

def admin_give_all_rating(amount):
    """Выдать всем рейтинг"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE projects SET rating = rating + ?', (amount,))
        affected = cursor.rowcount
        conn.commit()
        return affected
    finally:
        conn.close()

def admin_give_vip_to_all():
    """Выдать всем VIP"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE projects SET vip = 1')
        affected = cursor.rowcount
        conn.commit()
        return affected
    finally:
        conn.close()

def get_all_users_count():
    """Получить количество пользователей"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT COUNT(*) FROM projects')
        return cursor.fetchone()[0]
    finally:
        conn.close()

# ==================== ДОНАТ МАГАЗИН ====================
def buy_donation_item(user_id, item_name):
    """Покупка товара в донат магазине"""
    # Товары доната
    items = {
        'vip': ('VIP статус', 1000000, 'vip'),
        'x2': ('x2 доход на 24ч', 750000, 'bonus'),
        'shield': ('Щит от DDoS', 500000, 'protection'),
        'gold': ('Золотая реклама', 300000, 'ad'),
        'boost': ('Буст игроков', 400000, 'boost')
    }
    
    if item_name not in items:
        return False, "❌ Товар не найден"
    
    item_title, price, item_type = items[item_name]
    project = get_project(user_id=user_id)
    
    if project['balance'] < price:
        return False, f"❌ Недостаточно средств. Нужно: ${price:,.0f}"
    
    # Списание средств
    update_balance(user_id, -price)
    
    # Применяем эффект
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if item_type == 'vip':
            cursor.execute('UPDATE projects SET vip = 1 WHERE user_id = ?', (user_id,))
            effect = "✅ Теперь вы VIP игрок!"
        elif item_type == 'bonus':
            # Увеличиваем доход на 24 часа
            cursor.execute('UPDATE projects SET rating = rating + 2 WHERE user_id = ?', (user_id,))
            effect = "✅ Ваш доход увеличен в 2x на 24 часа!"
        elif item_type == 'protection':
            # Защита от DDoS на 12 часов
            effect = "✅ Защита от DDoS активирована на 12 часов!"
        elif item_type == 'ad':
            # Золотая реклама дает больше рейтинга
            cursor.execute('UPDATE projects SET rating = rating + 1.5, ads = ads + 1 WHERE user_id = ?', (user_id,))
            effect = "✅ Золотая реклама добавлена! +1.5⭐"
        elif item_type == 'boost':
            # Буст игроков
            cursor.execute('UPDATE projects SET players = players + 50 WHERE user_id = ?', (user_id,))
            effect = "✅ +50 игроков к вашему проекту!"
        
        # Записываем покупку
        cursor.execute('INSERT INTO donations (user_id, item_name, price) VALUES (?, ?, ?)',
                      (user_id, item_title, price))
        
        conn.commit()
        return True, f"✅ Куплено: {item_title}\n{effect}"
    finally:
        conn.close()
        # ==================== КОМАНДЫ БОТА ====================

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    text = f"""
🎮 **YANG TRAPPA Project Master**
Привет, {username}! Создай свой проект и стань лучшим!

🎁 **НОВЫМ ПОЛЬЗОВАТЕЛЯМ:**
Промокод: `YANGTRAPPA`
Активируй: /promo YANGTRAPPA
Получи: **350,000$** 💰

🔹 **Основные команды:**
/crmp <название> - Создать проект
/myproject - Моя статистика
/params - Параметры проекта
/shop - Магазин игроков
/ads - Реклама (1я: 10,000$, 2я: 10,500$...)
/top - Топ проектов
/ddos <название> - Атаковать
/bonus - Бонус раз в 3 часа
/promo <код> - Активировать промокод
/donateshop - Донат магазин

⚡ **Особенности:**
• Бонус каждые 3 часа
• Прогрессивная цена рекламы
• VIP статус за донат
"""
    
    # Добавляем админку если пользователь админ
    if user_id in ADMIN_IDS:
        text += "\n👑 **АДМИН ПАНЕЛЬ:** /adm"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['crmp'])
def create_project_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, "📝 Использование: /crmp НазваниеПроекта")
        return
    
    project_name = args[1]
    success, msg = create_project(user_id, username, project_name)
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['myproject'])
def my_project_cmd(message):
    user_id = message.from_user.id
    project = get_project(user_id=user_id)
    
    if not project:
        bot.send_message(message.chat.id, "❌ Сначала создайте проект: /crmp Название")
        return
    
    vip_status = "👑 VIP" if project['vip'] == 1 else "👤 Обычный"
    
    text = f"""
📊 **Проект: {project['project_name']}**

💰 Баланс: ${project['balance']:,.0f}
👥 Игроки: {project['players']}
🖥️ Хостинг: {project['hosting']}
⭐ Рейтинг: {project['rating']:.1f}
📢 Реклама: {project['ads']} (следующая: ${calculate_ad_price(user_id, project['ad_counter']):,.0f})
{vip_status}
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['params'])
def params_cmd(message):
    user_id = message.from_user.id
    project = get_project(user_id=user_id)
    
    if not project:
        bot.send_message(message.chat.id, "❌ Проект не найден")
        return
    
    # Получаем статистику атак
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) FROM attacks WHERE attacker_id = ? AND success = 1', (user_id,))
        attacks_success = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM attacks WHERE target_name = ?', (project['project_name'],))
        attacks_received = cursor.fetchone()[0]
    finally:
        conn.close()
    
    text = f"""
📈 **ПОЛНЫЕ ПАРАМЕТРЫ:**

🏷️ Название: {project['project_name']}
💰 Баланс: ${project['balance']:,.0f}
👥 Игроки: {project['players']}
🖥️ Хостинг: {project['hosting']}
⭐ Рейтинг: {project['rating']:.1f}
📢 Реклама: {project['ads']} (куплено: {project['ad_counter']})
📈 Уровень: {project['level']}

⚔️ **Атаки:**
• Успешных атак: {attacks_success}
• Получено атак: {attacks_received}

📅 Создан: {project['created_at'][:10]}
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['bonus'])
def bonus_cmd(message):
    user_id = message.from_user.id
    
    success, msg = daily_bonus(user_id)
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['ddos'])
def ddos_cmd(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, "⚔️ Использование: /ddos НазваниеПроекта\nПример: /ddos MyProject")
        return
    
    target = args[1]
    user_id = message.from_user.id
    
    success, msg = ddos_attack(user_id, target)
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['promo'])
def promo_cmd(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, "🎁 Использование: /promo КОД\nПример: /promo YANGTRAPPA")
        return
    
    code = args[1].upper()
    user_id = message.from_user.id
    
    success, msg = use_promocode(user_id, code)
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['top'])
def top_cmd(message):
    top = get_top_projects(10)
    
    if not top:
        bot.send_message(message.chat.id, "📊 Пока нет проектов")
        return
    
    text = "🏆 **ТОП 10 ПРОЕКТОВ:**\n\n"
    for i, project in enumerate(top, 1):
        vip = "👑 " if project.get('vip', 0) == 1 else ""
        text += f"{i}. {vip}**{project['project_name']}**\n"
        text += f"   💰 ${project['balance']:,.0f} | 👥 {project['players']} | ⭐ {project['rating']:.1f}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['shop'])
def shop_cmd(message):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("👥 100 игроков - $300,000", callback_data="buy_100"),
        types.InlineKeyboardButton("👥 250 игроков - $540,000", callback_data="buy_250"),
        types.InlineKeyboardButton("👥 300+ игроков - $600,000", callback_data="buy_300"),
        types.InlineKeyboardButton("🚀 Улучшить хостинг - $500,000", callback_data="buy_hosting")
    )
    bot.send_message(message.chat.id, "🛒 **МАГАЗИН ИГРОКОВ:**", reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['ads'])
def ads_cmd(message):
    user_id = message.from_user.id
    project = get_project(user_id=user_id)
    
    if not project:
        bot.send_message(message.chat.id, "❌ Сначала создайте проект!")
        return
    
    next_price = calculate_ad_price(user_id, project['ad_counter'])
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(f"📢 1 реклама - ${next_price:,.0f}", callback_data="buy_ad_1"),
        types.InlineKeyboardButton("💰 Купить на все деньги", callback_data="buy_ad_all"),
        types.InlineKeyboardButton(f"📈 Купить 5 реклам", callback_data="buy_ad_5")
    )
    
    text = f"""📢 **РЕКЛАМА**

💰 Стоимость рекламы растет:
• 1я: 10,000$
• 2я: 10,500$
• 3я: 11,000$
• И так далее (+500$ за каждую)

📊 Ваша статистика:
Куплено реклам: {project['ad_counter']}
Следующая реклама: **${next_price:,.0f}**
Каждая реклама дает +0.5⭐
"""
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='Markdown')

@bot.message_handler(commands=['donateshop'])
def donateshop_cmd(message):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("👑 VIP статус - $1,000,000", callback_data="donate_vip"),
        types.InlineKeyboardButton("⚡ x2 доход на 24ч - $750,000", callback_data="donate_x2"),
        types.InlineKeyboardButton("🛡️ Щит от DDoS - $500,000", callback_data="donate_shield"),
        types.InlineKeyboardButton("💰 Золотая реклама - $300,000", callback_data="donate_gold"),
        types.InlineKeyboardButton("🚀 Буст игроков +50 - $400,000", callback_data="donate_boost")
    )
    
    text = """🎮 **ДОНАТ МАГАЗИН**

Покупайте улучшения для быстрого прогресса!

👑 **VIP статус** - $1,000,000
• Специальный значок в топе
• +10% к доходу от рекламы

⚡ **x2 доход** - $750,000
• Удвоенный доход на 24 часа
• Работает на все виды прибыли

🛡️ **Щит от DDoS** - $500,000
• Защита от атак на 12 часов
• Шанс отражения атаки 90%

💰 **Золотая реклама** - $300,000
• Дает +1.5⭐ вместо обычных 0.5
• Не увеличивает счетчик реклам

🚀 **Буст игроков** - $400,000
• Мгновенно +50 игроков
• Увеличивает пассивный доход
"""
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='Markdown')

# ==================== АДМИН ПАНЕЛЬ ====================
@bot.message_handler(commands=['adm'])
def admin_panel(message):
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "❌ Доступ запрещен!")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💰 Выдать всем 300к", callback_data="admin_give_money"),
        types.InlineKeyboardButton("⭐ +3⭐ всем", callback_data="admin_give_rating"),
        types.InlineKeyboardButton("👑 VIP всем", callback_data="admin_give_vip"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    )
    
    bot.send_message(message.chat.id, "👑 **АДМИН ПАНЕЛЬ**", reply_markup=keyboard)

# ==================== ОБРАБОТКА КНОПОК ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # Магазин
    if call.data == "buy_100":
        success, msg = buy_players(user_id, '100')
        bot.answer_callback_query(call.id, msg)
    elif call.data == "buy_250":
        success, msg = buy_players(user_id, '250')
        bot.answer_callback_query(call.id, msg)
    elif call.data == "buy_300":
        success, msg = buy_players(user_id, '300')
        bot.answer_callback_query(call.id, msg)
    elif call.data == "buy_hosting":
        success, msg = upgrade_hosting(user_id)
        bot.answer_callback_query(call.id, msg)
    elif call.data == "buy_ad_1":
        success, msg = buy_ad(user_id, 1)
        bot.answer_callback_query(call.id, msg)
    elif call.data == "buy_ad_5":
        success, msg = buy_ad(user_id, 5)
        bot.answer_callback_query(call.id, msg)
    elif call.data == "buy_ad_all":
        success, msg = buy_ad(user_id, 1, True)
        bot.answer_callback_query(call.id, msg)
    
    # Донат магазин
    elif call.data.startswith("donate_"):
        item = call.data.replace("donate_", "")
        success, msg = buy_donation_item(user_id, item)
        bot.answer_callback_query(call.id, msg)
    
    # Админ панель
    elif user_id in ADMIN_IDS:
        if call.data == "admin_give_money":
            affected = admin_give_all_money(300000)
            bot.answer_callback_query(call.id, f"✅ Выдано $300,000 всем {affected} игрокам")
        elif call.data == "admin_give_rating":
            affected = admin_give_all_rating(3)
            bot.answer_callback_query(call.id, f"✅ Выдано +3⭐ всем {affected} игрокам")
        elif call.data == "admin_give_vip":
            affected = admin_give_vip_to_all()
            bot.answer_callback_query(call.id, f"✅ VIP выдан всем {affected} игрокам")
        elif call.data == "admin_stats":
            users = get_all_users_count()
            bot.answer_callback_query(call.id, f"📊 Всего игроков: {users}")

# ==================== ЗАПУСК БОТА ====================
print("🎮 YANG TRAPPA Project Master запускается...")
print("✅ База данных готова")
print("🎁 Промокод YANGTRAPPA создан")
print("💰 Система рекламы: 10,000$ + 500$ за каждую следующую")
print("⏰ Бонус раз в 3 часа")
print("👑 Админ панель доступна")
print("🚀 Бот запущен!")

bot.polling(none_stop=True)