# -*- coding: utf-8 -*-
import os
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
import telebot
from telebot import types

# ---------------- Конфигурация ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в .env")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)          # БД будет тут и не удалится при git pull
DB_PATH = os.path.join(DATA_DIR, "bot.db")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# Состояния и временные данные (в памяти)
user_states: dict[int, str] = {}
temp_data: dict[int, dict] = {}
contact_refs: dict[int, tuple[int, int]] = {}   # bot_msg_id -> (buyer_id, seller_id)


# ---------------- База данных ----------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT
    );
    CREATE TABLE IF NOT EXISTS stores(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER UNIQUE,
        name TEXT,
        about TEXT,
        photo_id TEXT,
        response TEXT
    );
    CREATE TABLE IF NOT EXISTS catalogs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        name TEXT
    );
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        catalog_id INTEGER,
        name TEXT,
        price REAL,
        quantity INTEGER
    );
    CREATE TABLE IF NOT EXISTS promocodes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        code TEXT
    );
    CREATE TABLE IF NOT EXISTS purchases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        store_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        price REAL,
        quantity INTEGER,
        pickup_time TEXT,
        pickup_place TEXT,
        customer_name TEXT,
        payment TEXT,
        promo TEXT,
        status TEXT DEFAULT 'new',
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()


init_db()


# ---------------- Хелперы БД ----------------
def ensure_user(uid, username=None):
    conn = db()
    conn.execute("INSERT OR IGNORE INTO users(user_id, username) VALUES (?,?)",
                 (uid, username or ""))
    if username:
        conn.execute("UPDATE users SET username=? WHERE user_id=?", (username, uid))
    conn.commit()
    conn.close()


def get_store_by_owner(uid):
    conn = db()
    row = conn.execute("SELECT * FROM stores WHERE owner_id=?", (uid,)).fetchone()
    conn.close()
    return row


def get_store_by_name(name):
    conn = db()
    row = conn.execute("SELECT * FROM stores WHERE name=?", (name,)).fetchone()
    conn.close()
    return row


def get_store_by_id(sid):
    conn = db()
    row = conn.execute("SELECT * FROM stores WHERE id=?", (sid,)).fetchone()
    conn.close()
    return row


def get_all_stores():
    conn = db()
    rows = conn.execute("SELECT * FROM stores").fetchall()
    conn.close()
    return rows


def get_catalogs(store_id):
    conn = db()
    rows = conn.execute("SELECT * FROM catalogs WHERE store_id=?", (store_id,)).fetchall()
    conn.close()
    return rows


def get_catalog_by_name(store_id, name):
    conn = db()
    row = conn.execute("SELECT * FROM catalogs WHERE store_id=? AND name=?",
                       (store_id, name)).fetchone()
    conn.close()
    return row


def get_catalog_by_id(cid):
    conn = db()
    row = conn.execute("SELECT * FROM catalogs WHERE id=?", (cid,)).fetchone()
    conn.close()
    return row


def get_products_by_catalog(cid, only_available=True):
    conn = db()
    q = "SELECT * FROM products WHERE catalog_id=?" + (" AND quantity>0" if only_available else "")
    rows = conn.execute(q, (cid,)).fetchall()
    conn.close()
    return rows


def get_products_by_store(sid, only_available=True):
    conn = db()
    q = "SELECT * FROM products WHERE store_id=?" + (" AND quantity>0" if only_available else "")
    rows = conn.execute(q, (sid,)).fetchall()
    conn.close()
    return rows


def get_product(pid):
    conn = db()
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    return row


def get_product_by_name(store_id, name):
    conn = db()
    row = conn.execute("SELECT * FROM products WHERE store_id=? AND name=?",
                       (store_id, name)).fetchone()
    conn.close()
    return row


# ---------------- Клавиатуры ----------------
def main_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛒 Купить")
    if get_store_by_owner(uid):
        kb.row("🏪 Мой магазин")
    else:
        kb.row("🏪 Создать магазин")
    kb.row("👤 Профиль")
    return kb


def store_menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎨 Поменять оформление")
    kb.row("💬 Добавить ответ")
    kb.row("📊 Статистика")
    kb.row("📦 Добавить товары")
    kb.row("🗂 Мои товары")
    kb.row("🎟 Добавить промокод")
    kb.row("🗑 Удалить магазин")
    kb.row("⬅️ Назад")
    return kb


def stores_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for s in get_all_stores():
        kb.row(f"🏬 {s['name']}")
    kb.row("⬅️ Назад")
    return kb


def catalogs_kb(store_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in get_catalogs(store_id):
        kb.row(f"📁 {c['name']}")
    kb.row("⬅️ Назад")
    return kb


def products_kb(catalog_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for p in get_products_by_catalog(catalog_id):
        kb.row(f"📦 {p['name']}")
    kb.row("⬅️ Назад")
    return kb


def payment_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💵 Наличные", "💳 Перевод")
    return kb


def promo_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("❌ Нет промокода")
    return kb


def confirm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✅ Подтвердить")
    kb.row("✏️ Изменить", "❌ Отменить")
    return kb


# ---------------- /start ----------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    uid = message.from_user.id
    ensure_user(uid, message.from_user.username)
    user_states.pop(uid, None)
    temp_data.pop(uid, None)
    bot.send_message(uid, "🏠 Главное меню", reply_markup=main_kb(uid))


# ---------------- Универсальный обработчик ----------------
@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    uid = message.from_user.id
    ensure_user(uid, message.from_user.username)
    text = (message.text or "").strip()

    # ---- Ответ на "контактное" сообщение бота ----
    if message.reply_to_message and message.reply_to_message.message_id in contact_refs:
        buyer_id, seller_id = contact_refs[message.reply_to_message.message_id]
        try:
            if text:
                bot.send_message(seller_id, f"✉️ Сообщение от покупателя (ID {uid}):\n\n{text}")
            else:
                bot.send_message(seller_id, f"✉️ Покупатель (ID {uid}) отправил медиа-сообщение.")
            bot.send_message(uid, "✅ Сообщение отправлено продавцу.")
        except Exception:
            bot.send_message(uid, "⚠️ Не удалось отправить сообщение продавцу.")
        return

    state = user_states.get(uid)

    # ================== СОЗДАНИЕ МАГАЗИНА ==================
    if state == "store_name":
        if not text:
            return bot.send_message(uid, "Напишите название текстом.")
        temp_data.setdefault(uid, {})["store_name"] = text
        user_states[uid] = "store_about"
        return bot.send_message(uid, "✏️ Напишите описание магазина (о себе):")

    if state == "store_about":
        if not text:
            return bot.send_message(uid, "Напишите описание текстом.")
        temp_data[uid]["store_about"] = text
        user_states[uid] = "store_photo"
        return bot.send_message(uid, "🖼 Отправьте фото магазина:")

    if state == "store_photo":
        if not message.photo:
            return bot.send_message(uid, "Пожалуйста, отправьте фото.")
        photo_id = message.photo[-1].file_id
        d = temp_data.get(uid, {})
        conn = db()
        conn.execute(
            "INSERT INTO stores(owner_id, name, about, photo_id) VALUES (?,?,?,?)",
            (uid, d.get("store_name"), d.get("store_about"), photo_id)
        )
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        temp_data.pop(uid, None)
        return bot.send_message(uid, "✅ Магазин создан!", reply_markup=main_kb(uid))

    # ================== ИЗМЕНЕНИЕ ОФОРМЛЕНИЯ ==================
    if state == "edit_choice":
        if text == "Название":
            user_states[uid] = "edit_name"
            return bot.send_message(uid, "Введите новое название:")
        if text == "Описание":
            user_states[uid] = "edit_about"
            return bot.send_message(uid, "Введите новое описание:")
        if text == "Фото":
            user_states[uid] = "edit_photo"
            return bot.send_message(uid, "Отправьте новое фото:")
        if text == "Отмена":
            user_states.pop(uid, None)
            return open_store_menu(uid)

    if state == "edit_name":
        conn = db()
        conn.execute("UPDATE stores SET name=? WHERE owner_id=?", (text, uid))
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        return open_store_menu(uid)

    if state == "edit_about":
        conn = db()
        conn.execute("UPDATE stores SET about=? WHERE owner_id=?", (text, uid))
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        return open_store_menu(uid)

    if state == "edit_photo":
        if not message.photo:
            return bot.send_message(uid, "Отправьте фото.")
        conn = db()
        conn.execute("UPDATE stores SET photo_id=? WHERE owner_id=?",
                     (message.photo[-1].file_id, uid))
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        return open_store_menu(uid)

    # ================== ОТВЕТ ПРОДАВЦА ==================
    if state == "seller_response":
        conn = db()
        conn.execute("UPDATE stores SET response=? WHERE owner_id=?", (text, uid))
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.send_message(uid, "✅ Ответ сохранён. Он будет отправлен покупателю после подтверждения покупки.")
        return open_store_menu(uid)

    # ================== ПРОМОКОД ==================
    if state == "promo_code":
        store = get_store_by_owner(uid)
        conn = db()
        conn.execute("INSERT INTO promocodes(store_id, code) VALUES (?,?)", (store["id"], text))
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.send_message(uid, f"✅ Промокод «{text}» добавлен.")
        return open_store_menu(uid)

    # ================== СОЗДАНИЕ КАТАЛОГА ==================
    if state == "catalog_name":
        store = get_store_by_owner(uid)
        conn = db()
        conn.execute("INSERT INTO catalogs(store_id, name) VALUES (?,?)", (store["id"], text))
        conn.commit()
        conn.close()
        user_states[uid] = "cat_manage"
        bot.send_message(uid, f"✅ Каталог «{text}» создан.\n\nВыберите каталог для управления:",
                         reply_markup=catalogs_kb(store["id"]))
        return

    # ================== УПРАВЛЕНИЕ КАТАЛОГОМ (клик по каталогу) ==================
    if state == "cat_manage":
        if text == "⬅️ Назад":
            user_states.pop(uid, None)
            return open_store_menu(uid)
        if text.startswith("📁 "):
            store = get_store_by_owner(uid)
            name = text[2:]
            cat = get_catalog_by_name(store["id"], name)
            if not cat:
                return bot.send_message(uid, "Каталог не найден.")
            temp_data.setdefault(uid, {})["current_catalog_id"] = cat["id"]
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"add_prod:{cat['id']}"),
                types.InlineKeyboardButton("🗑 Удалить товар", callback_data=f"del_prod:{cat['id']}"),
            )
            return bot.send_message(uid, f"Каталог: {cat['name']}\n\nЧто сделать?", reply_markup=markup)

    # ================== УДАЛЕНИЕ КАТАЛОГА ==================
    if state == "del_cat_select":
        if text == "⬅️ Назад":
            user_states.pop(uid, None)
            return open_store_menu(uid)
        if text.startswith("📁 "):
            store = get_store_by_owner(uid)
            cat = get_catalog_by_name(store["id"], text[2:])
            if not cat:
                return
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Да", callback_data=f"confirm_del_cat:{cat['id']}"),
                types.InlineKeyboardButton("❌ Нет", callback_data="cancel_del_cat"),
            )
            return bot.send_message(uid, f"Удалить каталог «{cat['name']}»?", reply_markup=markup)

    # ================== ДОБАВЛЕНИЕ ТОВАРА ==================
    if state == "add_prod_name":
        d = temp_data.setdefault(uid, {})
        d["p_name"] = text
        user_states[uid] = "add_prod_price"
        return bot.send_message(uid, "💰 Введите цену товара (число):")

    if state == "add_prod_price":
        try:
            price = float(text.replace(",", "."))
        except ValueError:
            return bot.send_message(uid, "Введите число, например 199.99")
        temp_data[uid]["p_price"] = price
        user_states[uid] = "add_prod_qty"
        return bot.send_message(uid, "📦 Введите количество товара (целое число):")

    if state == "add_prod_qty":
        try:
            qty = int(text)
        except ValueError:
            return bot.send_message(uid, "Введите целое число.")
        d = temp_data[uid]
        d["p_qty"] = qty
        user_states[uid] = "add_prod_confirm"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_add_prod"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_add_prod"),
        )
        info = f"Название: {d['p_name']}\nЦена: {d['p_price']}\nКоличество: {d['p_qty']}"
        return bot.send_message(uid, f"Подтвердить добавление?\n\n{info}", reply_markup=markup)

    # ================== ПОКУПКА ==================
    if state == "buy_time":
        temp_data[uid]["buy_time"] = text
        user_states[uid] = "buy_place"
        return bot.send_message(uid, "📍 Где будет удобно забрать?", reply_markup=types.ReplyKeyboardRemove())

    if state == "buy_place":
        temp_data[uid]["buy_place"] = text
        user_states[uid] = "buy_name"
        return bot.send_message(uid, "🙋 Ваше имя?")

    if state == "buy_name":
        temp_data[uid]["buy_name"] = text
        user_states[uid] = "buy_payment"
        return bot.send_message(uid, "💳 Оплата наличные или перевод?", reply_markup=payment_kb())

    if state == "buy_payment":
        if text not in ("💵 Наличные", "💳 Перевод"):
            return bot.send_message(uid, "Выберите на клавиатуре.", reply_markup=payment_kb())
        temp_data[uid]["buy_payment"] = text
        user_states[uid] = "buy_promo"
        return bot.send_message(uid, "🎟 Введите промокод или нажмите кнопку:",
                                reply_markup=promo_kb())

    if state == "buy_promo":
        if text == "❌ Нет промокода":
            temp_data[uid]["buy_promo"] = "—"
        else:
            temp_data[uid]["buy_promo"] = text
        user_states[uid] = "buy_confirm"
        d = temp_data[uid]
        summary = (
            f"🛍 Товар: {d['product_name']}\n"
            f"💰 Цена: {d['product_price']}\n"
            f"🕐 Время: {d['buy_time']}\n"
            f"📍 Место: {d['buy_place']}\n"
            f"🙋 Имя: {d['buy_name']}\n"
            f"💳 Оплата: {d['buy_payment']}\n"
            f"🎟 Промокод: {d['buy_promo']}"
        )
        return bot.send_message(uid, "Проверьте данные:\n\n" + summary, reply_markup=confirm_kb())

    if state == "buy_confirm":
        if text == "❌ Отменить":
            user_states.pop(uid, None)
            temp_data.pop(uid, None)
            return bot.send_message(uid, "Покупка отменена.", reply_markup=main_kb(uid))
        if text == "✏️ Изменить":
            user_states[uid] = "buy_time"
            return bot.send_message(uid, "🕐 В какое время будет удобно забрать?",
                                    reply_markup=types.ReplyKeyboardRemove())
        if text == "✅ Подтвердить":
            return finalize_purchase(uid)

    # ================== ГЛАВНОЕ МЕНЮ ==================
    if text == "🛒 Купить":
        stores = get_all_stores()
        if not stores:
            return bot.send_message(uid, "Пока нет ни одного магазина.")
        user_states[uid] = "buyer_stores"
        temp_data.pop(uid, None)
        return bot.send_message(uid, "Выберите магазин:", reply_markup=stores_kb())

    if text == "🏪 Создать магазин":
        if get_store_by_owner(uid):
            return open_store_menu(uid)
        user_states[uid] = "store_name"
        temp_data[uid] = {}
        return bot.send_message(uid, "📝 Введите название магазина:", reply_markup=types.ReplyKeyboardRemove())

    if text == "🏪 Мой магазин":
        return open_store_menu(uid)

    if text == "👤 Профиль":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🧾 Мои покупки")
        markup.row("⬅️ Назад")
        user_states[uid] = "profile"
        return bot.send_message(uid, "👤 Профиль", reply_markup=markup)

    # ---- Профиль ----
    if state == "profile":
        if text == "🧾 Мои покупки":
            conn = db()
            rows = conn.execute("SELECT * FROM purchases WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
            conn.close()
            if not rows:
                return bot.send_message(uid, "У вас пока нет покупок.")
            out = ["🧾 Ваши покупки:"]
            for r in rows:
                out.append(f"• {r['product_name']} — {r['price']}₽, статус: {r['status']}")
            return bot.send_message(uid, "\n".join(out))
        if text == "⬅️ Назад":
            user_states.pop(uid, None)
            return bot.send_message(uid, "🏠 Главное меню", reply_markup=main_kb(uid))

    # ---- Меню магазина продавца ----
    if state == "store_menu":
        if text == "⬅️ Назад":
            user_states.pop(uid, None)
            return bot.send_message(uid, "🏠 Главное меню", reply_markup=main_kb(uid))
        if text == "🎨 Поменять оформление":
            kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row("Название", "Описание")
            kb.row("Фото", "Отмена")
            user_states[uid] = "edit_choice"
            return bot.send_message(uid, "Что изменить?", reply_markup=kb)
        if text == "💬 Добавить ответ":
            user_states[uid] = "seller_response"
            return bot.send_message(uid, "Напишите сообщение, которое получит покупатель после подтверждения покупки:")
        if text == "📊 Статистика":
            return show_statistics(uid)
        if text == "📦 Добавить товары":
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("➕ Создать каталог", callback_data="create_cat"),
                types.InlineKeyboardButton("🗑 Удалить каталог", callback_data="del_cat_menu"),
            )
            return bot.send_message(uid, "Управление каталогами:", reply_markup=markup)
        if text == "🗂 Мои товары":
            store = get_store_by_owner(uid)
            prods = get_products_by_store(store["id"], only_available=False)
            if not prods:
                return bot.send_message(uid, "Товаров пока нет.")
            out = ["🗂 Ваши товары:"]
            for p in prods:
                cat = get_catalog_by_id(p["catalog_id"])
                out.append(f"• {p['name']} — {p['price']}₽, остаток: {p['quantity']} (каталог: {cat['name'] if cat else '—'})")
            return bot.send_message(uid, "\n".join(out))
        if text == "🎟 Добавить промокод":
            user_states[uid] = "promo_code"
            return bot.send_message(uid, "Введите промокод:")
        if text == "🗑 Удалить магазин":
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_del_store"),
                types.InlineKeyboardButton("❌ Нет", callback_data="cancel_del_store"),
            )
            return bot.send_message(uid, "Точно удалить магазин?", reply_markup=markup)

    # ---- Навигация покупателя ----
    if state == "buyer_stores":
        if text == "⬅️ Назад":
            user_states.pop(uid, None)
            return bot.send_message(uid, "🏠 Главное меню", reply_markup=main_kb(uid))
        if text.startswith("🏬 "):
            store = get_store_by_name(text[2:])
            if not store:
                return
            temp_data[uid] = {"store_id": store["id"]}
            user_states[uid] = "buyer_store"
            return show_store(uid, store)

    if state == "buyer_store":
        d = temp_data.get(uid, {})
        store = get_store_by_id(d.get("store_id"))
        if not store:
            user_states.pop(uid, None)
            return bot.send_message(uid, "Магазин не найден.", reply_markup=main_kb(uid))
        if text == "⬅️ Назад":
            user_states[uid] = "buyer_stores"
            return bot.send_message(uid, "Выберите магазин:", reply_markup=stores_kb())
        if text.startswith("📁 "):
            cat = get_catalog_by_name(store["id"], text[2:])
            if not cat:
                return
            d["catalog_id"] = cat["id"]
            user_states[uid] = "buyer_catalog"
            prods = get_products_by_catalog(cat["id"])
            if not prods:
                bot.send_message(uid, "В этом каталоге пока нет товаров.")
            return bot.send_message(uid, f"📁 {cat['name']}\nВыберите товар:",
                                    reply_markup=products_kb(cat["id"]))

    if state == "buyer_catalog":
        d = temp_data.get(uid, {})
        store = get_store_by_id(d.get("store_id"))
        if text == "⬅️ Назад":
            user_states[uid] = "buyer_store"
            return show_store(uid, store)
        if text.startswith("📦 "):
            p = get_product_by_name(store["id"], text[2:])
            if not p:
                return
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🛒 Купить", callback_data=f"buy:{p['id']}"),
                types.InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_buy:{p['id']}"),
            )
            return bot.send_message(
                uid,
                f"📦 {p['name']}\n💰 Цена: {p['price']}\n📊 В наличии: {p['quantity']}",
                reply_markup=markup
            )


# ---------------- Вспомогательные UI-функции ----------------
def open_store_menu(uid):
    store = get_store_by_owner(uid)
    if not store:
        user_states.pop(uid, None)
        return bot.send_message(uid, "Магазин не найден.", reply_markup=main_kb(uid))
    caption = f"🏪 {store['name']}\n\n{store['about']}"
    try:
        if store["photo_id"]:
            bot.send_photo(uid, store["photo_id"], caption=caption)
        else:
            bot.send_message(uid, caption)
    except Exception:
        bot.send_message(uid, caption)
    user_states[uid] = "store_menu"
    bot.send_message(uid, "Меню магазина:", reply_markup=store_menu_kb())


def show_store(uid, store):
    prods = get_products_by_store(store["id"])
    lines = [f"🏪 {store['name']}", "", store["about"] or "", "", "Товары:"]
    if prods:
        for p in prods:
            lines.append(f"• {p['name']} — {p['price']}₽ (в наличии: {p['quantity']})")
    else:
        lines.append("— пока пусто —")
    text = "\n".join(lines)
    try:
        if store["photo_id"]:
            bot.send_photo(uid, store["photo_id"], caption=text[:1024], reply_markup=catalogs_kb(store["id"]))
        else:
            bot.send_message(uid, text, reply_markup=catalogs_kb(store["id"]))
    except Exception:
        bot.send_message(uid, text, reply_markup=catalogs_kb(store["id"]))


def show_statistics(uid):
    store = get_store_by_owner(uid)
    conn = db()
    rows = conn.execute(
        "SELECT * FROM purchases WHERE store_id=? AND status='confirmed' ORDER BY id DESC",
        (store["id"],)
    ).fetchall()
    conn.close()
    if not rows:
        return bot.send_message(uid, "📊 Пока нет подтверждённых покупок.")
    total = 0.0
    out = ["📊 Статистика продаж:"]
    for r in rows:
        out.append(f"• {r['product_name']} × {r['quantity']} — {r['price']}₽")
        total += float(r["price"]) * int(r["quantity"])
    out.append(f"\n💰 Общая выручка: {total}₽")
    bot.send_message(uid, "\n".join(out))


def finalize_purchase(uid):
    d = temp_data.get(uid, {})
    if not d.get("product_id"):
        user_states.pop(uid, None)
        return bot.send_message(uid, "Ошибка: товар не найден.", reply_markup=main_kb(uid))

    store = get_store_by_id(d["store_id"])
    seller_id = store["owner_id"]

    conn = db()
    conn.execute("""INSERT INTO purchases(
        user_id, store_id, product_id, product_name, price, quantity,
        pickup_time, pickup_place, customer_name, payment, promo, status, created_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, d["store_id"], d["product_id"], d["product_name"], d["product_price"],
         1, d["buy_time"], d["buy_place"], d["buy_name"], d["buy_payment"],
         d["buy_promo"], "new", datetime.now().isoformat(timespec="seconds")))
    pid = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.commit()
    conn.close()

    user_states.pop(uid, None)
    temp_data.pop(uid, None)

    bot.send_message(uid, "✅ Покупка успешно создана! Продавец свяжется с вами в ближайшее время.",
                     reply_markup=main_kb(uid))

    msg = bot.send_message(
        uid,
        "Если хотите связаться с продавцом, ответьте на это сообщение тем, что хотели бы написать продавцу."
    )
    contact_refs[msg.message_id] = (uid, seller_id)

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"accept:{pid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{pid}"),
    )
    try:
        bot.send_message(
            seller_id,
            f"🛒 Новая покупка!\n\n"
            f"Товар: {d['product_name']}\n"
            f"Цена: {d['product_price']}\n"
            f"Покупатель: {d['buy_name']} (ID {uid})\n"
            f"Время: {d['buy_time']}\n"
            f"Место: {d['buy_place']}\n"
            f"Оплата: {d['buy_payment']}\n"
            f"Промокод: {d['buy_promo']}",
            reply_markup=markup
        )
    except Exception:
        pass


# ---------------- CALLBACKS ----------------
@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    uid = call.from_user.id
    data = call.data

    # ---- Покупка: нажали "Купить" на карточке товара ----
    if data.startswith("buy:"):
        pid = int(data.split(":")[1])
        p = get_product(pid)
        if not p or p["quantity"] <= 0:
            return bot.answer_callback_query(call.id, "Товар недоступен")
        temp_data[uid] = {
            "product_id": pid,
            "product_name": p["name"],
            "product_price": p["price"],
            "store_id": p["store_id"],
        }
        user_states[uid] = "buy_time"
        bot.answer_callback_query(call.id)
        return bot.send_message(uid, "🕐 В какое время будет удобно забрать?",
                                reply_markup=types.ReplyKeyboardRemove())

    # ---- Отмена покупки ----
    if data.startswith("cancel_buy:"):
        pid = int(data.split(":")[1])
        p = get_product(pid)
        if p:
            cat = get_catalog_by_id(p["catalog_id"])
            user_states[uid] = "buyer_catalog"
            temp_data.setdefault(uid, {})["catalog_id"] = p["catalog_id"]
            temp_data[uid]["store_id"] = p["store_id"]
            bot.answer_callback_query(call.id, "Отменено")
            bot.send_message(uid, f"📁 {cat['name']}\nВыберите товар:",
                             reply_markup=products_kb(p["catalog_id"]))
        else:
            bot.answer_callback_query(call.id, "Отменено")
        return

    # ---- Создать каталог ----
    if data == "create_cat":
        user_states[uid] = "catalog_name"
        bot.answer_callback_query(call.id)
        return bot.send_message(uid, "Введите название каталога:")

    # ---- Меню "Удалить каталог" ----
    if data == "del_cat_menu":
        store = get_store_by_owner(uid)
        cats = get_catalogs(store["id"])
        if not cats:
            bot.answer_callback_query(call.id, "Нет каталогов")
            return bot.send_message(uid, "Каталогов нет.")
        user_states[uid] = "del_cat_select"
        bot.answer_callback_query(call.id)
        return bot.send_message(uid, "Выберите каталог для удаления:",
                                reply_markup=catalogs_kb(store["id"]))

    # ---- Подтверждение удаления каталога ----
    if data.startswith("confirm_del_cat:"):
        cid = int(data.split(":")[1])
        conn = db()
        conn.execute("DELETE FROM products WHERE catalog_id=?", (cid,))
        conn.execute("DELETE FROM catalogs WHERE id=?", (cid,))
        conn.commit()
        conn.close()
        user_states.pop(uid, None)
        bot.answer_callback_query(call.id, "Удалено")
        return open_store_menu(uid)

    if data == "cancel_del_cat":
        user_states.pop(uid, None)
        bot.answer_callback_query(call.id, "Отменено")
        return open_store_menu(uid)

    # ---- Добавить товар в каталог ----
    if data.startswith("add_prod:"):
        cid = int(data.split(":")[1])
        temp_data.setdefault(uid, {})["current_catalog_id"] = cid
        user_states[uid] = "add_prod_name"
        bot.answer_callback_query(call.id)
        return bot.send_message(uid, "📝 Введите название товара:")

    # ---- Удалить товар ----
    if data.startswith("del_prod:"):
        cid = int(data.split(":")[1])
        prods = get_products_by_catalog(cid, only_available=False)
        if not prods:
            bot.answer_callback_query(call.id, "Нет товаров")
            return
        markup = types.InlineKeyboardMarkup()
        for p in prods:
            markup.add(types.InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"del_prod_do:{p['id']}"))
        bot.answer_callback_query(call.id)
        return bot.send_message(uid, "Выберите товар для удаления:", reply_markup=markup)

    if data.startswith("del_prod_do:"):
        pid = int(data.split(":")[1])
        conn = db()
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Удалено")
        return bot.send_message(uid, "🗑 Товар удалён.")

    # ---- Подтверждение добавления товара ----
    if data == "confirm_add_prod":
        d = temp_data.get(uid, {})
        cid = d.get("current_catalog_id")
        store = get_store_by_owner(uid)
        conn = db()
        conn.execute(
            "INSERT INTO products(store_id, catalog_id, name, price, quantity) VALUES (?,?,?,?,?)",
            (store["id"], cid, d["p_name"], d["p_price"], d["p_qty"])
        )
        conn.commit()
        conn.close()
        user_states[uid] = "cat_manage"
        bot.answer_callback_query(call.id, "Товар добавлен")
        return bot.send_message(uid, "✅ Товар добавлен.\nВыберите каталог для управления:",
                                reply_markup=catalogs_kb(store["id"]))

    if data == "cancel_add_prod":
        user_states[uid] = "cat_manage"
        store = get_store_by_owner(uid)
        bot.answer_callback_query(call.id, "Отменено")
        return bot.send_message(uid, "Отменено.\nВыберите каталог:",
                                reply_markup=catalogs_kb(store["id"]))

    # ---- Продавец подтверждает покупку ----
    if data.startswith("accept:"):
        pid = int(data.split(":")[1])
        conn = db()
        row = conn.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone()
        if not row:
            conn.close()
            return bot.answer_callback_query(call.id, "Покупка не найдена")
        conn.execute("UPDATE purchases SET status='confirmed' WHERE id=?", (pid,))
        # Уменьшаем остаток
        prod = conn.execute("SELECT * FROM products WHERE id=?", (row["product_id"],)).fetchone()
        if prod:
            new_qty = max(0, int(prod["quantity"]) - int(row["quantity"]))
            conn.execute("UPDATE products SET quantity=? WHERE id=?", (new_qty, prod["id"]))
        conn.commit()
        conn.close()

        store = get_store_by_id(row["store_id"])
        buyer_id = row["user_id"]
        bot.answer_callback_query(call.id, "Подтверждено")

        # Отправляем покупателю сообщение продавца
        response = store["response"] if store else None
        try:
            if response:
                bot.send_message(buyer_id, response)
            else:
                bot.send_message(buyer_id, "✅ Продавец подтвердил вашу покупку.")
        except Exception:
            pass

        try:
            bot.send_message(uid, "✅ Покупка подтверждена, покупатель уведомлён.")
        except Exception:
            pass
        return

    # ---- Продавец отклоняет покупку ----
    if data.startswith("reject:"):
        pid = int(data.split(":")[1])
        conn = db()
        row = conn.execute("SELECT * FROM purchases WHERE id=?", (pid,)).fetchone()
        if not row:
            conn.close()
            return bot.answer_callback_query(call.id, "Покупка не найдена")
        conn.execute("UPDATE purchases SET status='rejected' WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "Отклонено")
        try:
            bot.send_message(row["user_id"], "❌ К сожалению, продавец отклонил покупку.")
        except Exception:
            pass
        return

    # ---- Удаление магазина ----
    if data == "confirm_del_store":
        store = get_store_by_owner(uid)
        if store:
            conn = db()
            conn.execute("DELETE FROM products WHERE store_id=?", (store["id"],))
            conn.execute("DELETE FROM catalogs WHERE store_id=?", (store["id"],))
            conn.execute("DELETE FROM promocodes WHERE store_id=?", (store["id"],))
            conn.execute("DELETE FROM stores WHERE id=?", (store["id"],))
            conn.commit()
            conn.close()
        user_states.pop(uid, None)
        bot.answer_callback_query(call.id, "Удалено")
        return bot.send_message(uid, "🗑 Магазин удалён.", reply_markup=main_kb(uid))

    if data == "cancel_del_store":
        bot.answer_callback_query(call.id, "Отменено")
        return


# ---------------- Запуск ----------------
if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling(skip_pending=True)