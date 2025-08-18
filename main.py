"""
Sport City Mr - Telegram bot (Aiogram 2.25.2)
Features implemented in a single `main.py` file:
- SQLite DB with tables: users, products, product_images
- Admins configured by TELEGRAM IDs
- /start with reply keyboard (all commands as buttons)
- /add (admin only) to add a product (supports up to 3 images)
- /products shows products as InlineKeyboard buttons
- Clicking a product shows image + nicely formatted info
  with inline buttons under the message: ✏️ Tahrirlash, 🗑 O'chirish (admins)
- Edit/Delete available via inline callbacks and also via /edit and /delete commands
- /search works by name or model (via args or interactive prompt)
- /db (admin only) shows Users and Products summary
- Basic pagination for /products (simple next/prev)

Requirements: aiogram==2.25.2
Replace API_TOKEN with your bot token.
"""

import logging
import sqlite3
import asyncio
from typing import List, Optional
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton,
                           ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove)
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# ================== CONFIG ==================
API_TOKEN = "8333601566:AAF4qNEhZDzpA7zZrnd3PhOsemi2qWu3V6s"
# default admins (replace with your admin IDs)
ADMINS = [807995985, 5751536492, 7435391786, 266461241]
DB_PATH = "sport_city.db"
PRODUCTS_PER_PAGE = 10

# ================ LOGGING ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================ BOT SETUP ==================
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ================ DATABASE ==================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # users
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            telegram_name TEXT,
            age INTEGER
        )"""
    )
    # products
    cur.execute(
        """CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            name TEXT,
            price TEXT,
            model TEXT,
            made_in TEXT,
            size_available INTEGER DEFAULT 0,
            size TEXT
        )"""
    )
    # product images (allow up to 3 images per product)
    cur.execute(
        """CREATE TABLE IF NOT EXISTS product_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            file_id TEXT,
            position INTEGER
        )"""
    )
    conn.commit()
    conn.close()

init_db()

# ================ STATES =====================
class AddProduct(StatesGroup):
    name = State()
    price = State()
    model = State()
    made_in = State()
    size_available = State()
    size = State()
    images = State()  # will collect up to 3 photos

class EditProduct(StatesGroup):
    product_id = State()
    field = State()  # which field admin wants to edit
    value = State()

class SearchState(StatesGroup):
    waiting_query = State()

# ================ HELPERS ====================
def db_query(query: str, params: tuple = (), fetch: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    data = None
    if fetch:
        data = cur.fetchall()
    conn.commit()
    conn.close()
    return data

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# ================ KEYBOARDS ==================

def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📦 Mahsulotlar"))
    kb.add(KeyboardButton("🔍 Qidirish"))
    if is_admin(user_id):
        kb.add(KeyboardButton("➕ Mahsulot qo'shish"))
        kb.add(KeyboardButton("📂 Ma'lumotlar bazasi"))
    kb.add(KeyboardButton("ℹ️ Bot haqida"))
    return kb

# small helper to build product inline list by page
def products_list_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    offset = page * PRODUCTS_PER_PAGE
    rows = db_query("SELECT id, name FROM products ORDER BY id DESC LIMIT ? OFFSET ?", (PRODUCTS_PER_PAGE, offset), fetch=True)
    kb = InlineKeyboardMarkup(row_width=1)
    for r in rows:
        pid, name = r
        kb.add(InlineKeyboardButton(f"{name} (ID:{pid})", callback_data=f"product_{pid}"))
    # pagination
    # simple prev/next only
    prev_offset = max(0, page - 1)
    next_offset = page + 1
    nav = InlineKeyboardMarkup(row_width=2)
    if page > 0:
        kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data=f"products_page_{prev_offset}"))
    # check if next page exists
    next_rows = db_query("SELECT id FROM products ORDER BY id DESC LIMIT 1 OFFSET ?", (PRODUCTS_PER_PAGE * next_offset,), fetch=True)
    if next_rows:
        kb.add(InlineKeyboardButton("Keyingi ➡️", callback_data=f"products_page_{next_offset}"))
    return kb

# build product action buttons (seen under an opened product)
def product_action_kb(product_id: int, user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_list"))
    if is_admin(user_id):
        kb.add(InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_{product_id}"))
        kb.add(InlineKeyboardButton("🗑 O'chirish", callback_data=f"delete_{product_id}"))
    return kb

# ================ HANDLERS ==================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # save user if not exists
    db_query("INSERT OR IGNORE INTO users (telegram_id, telegram_name) VALUES (?,?)", (message.from_user.id, message.from_user.full_name))
    kb = main_menu_keyboard(message.from_user.id)
    await message.answer("👋 Sport City Mr - xush kelibsiz!\n\nQuyidagi tugmalardan foydalaning:", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "📦 Mahsulotlar")
async def menu_products(message: types.Message):
    kb = products_list_keyboard(page=0)
    await message.answer("📦 Mahsulotlar ro'yxati (bosib ko'rish):", reply_markup=kb)

# pagination handler
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("products_page_"))
async def products_page_cb(call: types.CallbackQuery):
    page = int(call.data.split("_")[-1])
    kb = products_list_keyboard(page=page)
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

@dp.callback_query_handler(lambda c: c.data == "back_to_list")
async def back_to_list_cb(call: types.CallbackQuery):
    kb = products_list_keyboard(page=0)
    await call.message.answer("📦 Orqaga — mahsulotlar:", reply_markup=kb)
    await call.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("product_"))
async def show_product_cb(call: types.CallbackQuery):
    pid = int(call.data.split("_")[-1])
    rows = db_query("SELECT name, price, model, made_in, size_available, size FROM products WHERE id=?", (pid,), fetch=True)
    if not rows:
        await call.answer("Mahsulot topilmadi", show_alert=True)
        return
    name, price, model, made_in, size_available, size = rows[0]
    # get images
    imgs = db_query("SELECT file_id FROM product_images WHERE product_id=? ORDER BY position", (pid,), fetch=True)
    caption = f"📌 <b>{name}</b>\n\n💰 Narxi: {price}\n🔢 Model: {model}\n🏭 Qayerda: {made_in}\n"
    if size_available:
        caption += f"📏 O'lcham: {size}\n"
    caption += f"\n🆔 Mahsulot ID: {pid}"

    kb = product_action_kb(pid, call.from_user.id)
    if imgs:
        # send media group if more than 1
        if len(imgs) == 1:
            await bot.send_photo(call.message.chat.id, imgs[0][0], caption=caption, reply_markup=kb, parse_mode='HTML')
        else:
            media = []
            for i, item in enumerate(imgs):
                file_id = item[0]
                if i == 0:
                    media.append(types.InputMediaPhoto(media=file_id, caption=caption, parse_mode='HTML'))
                else:
                    media.append(types.InputMediaPhoto(media=file_id))
            await bot.send_media_group(call.message.chat.id, media)
            # after media group, send action buttons as separate message (Telegram limitation)
            await call.message.reply("", reply_markup=kb)
    else:
        await call.message.answer(caption, reply_markup=kb, parse_mode='HTML')
    await call.answer()

# ===== ADD PRODUCT FLOW =====
@dp.message_handler(lambda m: m.text == "➕ Mahsulot qo'shish", content_types=types.ContentTypes.TEXT)
async def add_product_button(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Siz admin emassiz.")
        return
    await message.answer("📌 Mahsulot nomini kiriting:", reply_markup=ReplyKeyboardRemove())
    await AddProduct.name.set()

@dp.message_handler(state=AddProduct.name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("💰 Mahsulot narxini kiriting:")
    await AddProduct.price.set()

@dp.message_handler(state=AddProduct.price)
async def add_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("🔢 Modelini kiriting:")
    await AddProduct.model.set()

@dp.message_handler(state=AddProduct.model)
async def add_model(message: types.Message, state: FSMContext):
    await state.update_data(model=message.text)
    await message.answer("🏭 Qayerda ishlab chiqarilgan?")
    await AddProduct.made_in.set()

@dp.message_handler(state=AddProduct.made_in)
async def add_made_in(message: types.Message, state: FSMContext):
    await state.update_data(made_in=message.text)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("Bor"), KeyboardButton("Yo'q"))
    await message.answer("📏 O'lcham mavjudmi? (Bor/Yo'q)", reply_markup=kb)
    await AddProduct.size_available.set()

@dp.message_handler(state=AddProduct.size_available)
async def add_size_available(message: types.Message, state: FSMContext):
    text = message.text.strip().lower()
    if text not in ("bor", "yo'q", "yox", "yoq"):
        await message.answer("Iltimos 'Bor' yoki 'Yo'q' deb yozing.")
        return
    has_size = 1 if text.startswith('b') else 0
    await state.update_data(size_available=has_size)
    if has_size:
        await message.answer("🔢 O'lchamni yozing (masalan: S,M,L yoki 42):", reply_markup=ReplyKeyboardRemove())
        await AddProduct.size.set()
    else:
        await state.update_data(size='')
        await message.answer("🖼 Mahsulot rasmlarini yuboring (1-3 ta). Yakunlash uchun /done yuboring.")
        await AddProduct.images.set()

@dp.message_handler(state=AddProduct.size)
async def add_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("🖼 Endi mahsulot rasmlarini yuboring (1-3 ta). Yakunlash uchun /done yuboring.")
    await AddProduct.images.set()

# collect photos (up to 3)
@dp.message_handler(content_types=['photo'], state=AddProduct.images)
async def add_images(message: types.Message, state: FSMContext):
    data = await state.get_data()
    imgs: List[str] = data.get('images', [])
    if len(imgs) >= 3:
        await message.answer("✅ Siz maksimal 3 ta rasm topshirgansiz. /done bilan yakunlang yoki /cancel")
        return
    file_id = message.photo[-1].file_id
    imgs.append(file_id)
    await state.update_data(images=imgs)
    await message.answer(f"Rasm qabul qilindi. Jami rasm: {len(imgs)}")

@dp.message_handler(commands=['done'], state=AddProduct.images)
async def finish_adding(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    price = data.get('price')
    model = data.get('model')
    made_in = data.get('made_in')
    size_available = data.get('size_available', 0)
    size = data.get('size', '')
    images = data.get('images', [])
    if not (name and price and model and images is not None):
        await message.answer("❌ Ba'zi ma'lumotlar yetishmaydi. /cancel bilan bekor qiling va qayta urinib ko'ring.")
        await state.finish()
        return
    # insert product
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO products (admin_id, name, price, model, made_in, size_available, size) VALUES (?,?,?,?,?,?,?)",
                (message.from_user.id, name, price, model, made_in, size_available, size))
    pid = cur.lastrowid
    # save images
    for idx, fid in enumerate(images[:3]):
        cur.execute("INSERT INTO product_images (product_id, file_id, position) VALUES (?,?,?)", (pid, fid, idx))
    conn.commit()
    conn.close()
    await state.finish()
    kb = main_menu_keyboard(message.from_user.id)
    await message.answer(f"✅ Mahsulot qo'shildi! ID: {pid}", reply_markup=kb)

@dp.message_handler(commands=['cancel'], state='*')
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("🛑 Operatsiya bekor qilindi.", reply_markup=main_menu_keyboard(message.from_user.id))

# ============= DELETE via Callback ==============
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("delete_"))
async def callback_delete(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("❌ Siz admin emassiz!", show_alert=True)
        return
    pid = int(c.data.split("_")[-1])
    # delete product and images
    db_query("DELETE FROM product_images WHERE product_id=?", (pid,))
    db_query("DELETE FROM products WHERE id=?", (pid,))
    await c.message.reply(f"🗑 Mahsulot ID {pid} o'chirildi.")
    await c.answer()

# ============= EDIT via Callback ==============
# Tugmalarni to‘g‘ri field nomlari bilan yuboramiz
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("edit_"))
async def callback_edit(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    parts = c.data.split("_")

    # Faqat edit_{pid} bo‘lsa
    if len(parts) == 2:
        pid = int(parts[1])

        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("Nomi", callback_data=f"editfield_{pid}_name"))
        kb.add(InlineKeyboardButton("Narxi", callback_data=f"editfield_{pid}_price"))
        kb.add(InlineKeyboardButton("Model", callback_data=f"editfield_{pid}_model"))
        kb.add(InlineKeyboardButton("Made in", callback_data=f"editfield_{pid}_made_in"))
        kb.add(InlineKeyboardButton("Rasm(lar)", callback_data=f"editfield_{pid}_images"))
        kb.add(InlineKeyboardButton("Bekor", callback_data="edit_cancel"))

        await c.message.reply("✏️ Qaysi maydonni tahrirlashni xohlaysiz?", reply_markup=kb)
    else:
        await c.answer("❌ Xato tugma!", show_alert=True)

    await c.answer()


# Fieldni olish
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("editfield_"))
async def callback_edit_field(c: types.CallbackQuery, state: FSMContext):
    # format: editfield_{pid}_{field}
    parts = c.data.split("_")
    pid = int(parts[1])
    field = parts[2]

    await state.update_data(product_id=pid, field=field)

    if field == 'name':
        await c.message.reply("✏️ Yangi nomni kiriting:")
        await EditProduct.field.set()
    elif field == 'price':
        await c.message.reply("💰 Yangi narxni kiriting:")
        await EditProduct.field.set()
    elif field == 'model':
        await c.message.reply("🔢 Yangi modelni kiriting:")
        await EditProduct.field.set()
    elif field == 'madein':
        await state.update_data(field='made_in')  # bazada made_in
        await c.message.reply("🏭 Yangi joyni kiriting:")
        await EditProduct.field.set()
    elif field == 'images':
        await c.message.reply("🖼 Rasm(lar) yuboring (1-3 ta). Yakunlash uchun /done yuboring.")
        await EditProduct.value.set()
    else:
        await c.answer("❌ Noma'lum maydon", show_alert=True)

    await c.answer()


@dp.callback_query_handler(lambda c: c.data == 'edit_cancel')
async def edit_cancel_cb(c: types.CallbackQuery):
    await c.message.reply("✖️ Tahrirlash bekor qilindi.")
    await c.answer()

@dp.message_handler(state=EditProduct.field)
async def edit_receive_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get('product_id')
    field = data.get('field')
    new_value = message.text

    if field not in ('name', 'price', 'model', 'made_in'):
        await message.answer("❌ Noma'lum maydon")
        await state.finish()
        return

    db_query(f"UPDATE products SET {field}=? WHERE id=?", (new_value, pid))
    await message.answer("✅ Maydon yangilandi.")
    await state.finish()


# ============= /edit and /delete commands (admin only) ==============
@dp.message_handler(commands=['edit'], commands_prefix='/', user_id=ADMINS)
async def cmd_edit(message: types.Message):
    # expects: /edit <id>
    args = message.get_args().strip()
    if not args.isdigit():
        await message.answer("✏️ Foydalanish: /edit <product_id>")
        return
    pid = int(args)
    # show quick inline to choose field
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("Nomi", callback_data=f"edit_field_{pid}_name"))
    kb.add(InlineKeyboardButton("Narxi", callback_data=f"edit_field_{pid}_price"))
    kb.add(InlineKeyboardButton("Model", callback_data=f"edit_field_{pid}_model"))
    kb.add(InlineKeyboardButton("Made in", callback_data=f"edit_field_{pid}_madein"))
    kb.add(InlineKeyboardButton("Rasm(lar)", callback_data=f"edit_field_{pid}_images"))
    await message.answer("✏️ Qaysi maydonni tahrirlashni xohlaysiz?", reply_markup=kb)

@dp.message_handler(commands=['delete'], commands_prefix='/', user_id=ADMINS)
async def cmd_delete(message: types.Message):
    args = message.get_args().strip()
    if not args.isdigit():
        await message.answer("🗑 Foydalanish: /delete <product_id>")
        return
    pid = int(args)
    db_query("DELETE FROM product_images WHERE product_id=?", (pid,))
    db_query("DELETE FROM products WHERE id=?", (pid,))
    await message.answer(f"🗑 Mahsulot ID {pid} o'chirildi.")

# ============= SEARCH ==============
@dp.message_handler(lambda m: m.text == "🔍 Qidirish")
async def search_button(message: types.Message):
    await message.answer("🔍 Qidirish: nom yoki model bo'yicha qidirish uchun so'rov yozing (yoki /search <so'z>)")
    await SearchState.waiting_query.set()

@dp.message_handler(commands=['search'])
async def cmd_search(message: types.Message):
    args = message.get_args().strip()
    if not args:
        await message.answer("🔍 Foydalanish: /search <so'z>")
        return
    query = f"%{args}%"
    rows = db_query("SELECT id, name, price, model FROM products WHERE name LIKE ? OR model LIKE ?", (query, query), fetch=True)
    if not rows:
        await message.answer("📭 Hech narsa topilmadi.")
        return
    kb = InlineKeyboardMarkup()
    for r in rows:
        kb.add(InlineKeyboardButton(f"{r[1]} (ID:{r[0]})", callback_data=f"product_{r[0]}"))
    await message.answer(f"🔎 Topildi: {len(rows)} ta", reply_markup=kb)

@dp.message_handler(state=SearchState.waiting_query)
async def search_text(message: types.Message, state: FSMContext):
    query = f"%{message.text}%"
    rows = db_query("SELECT id, name, price, model FROM products WHERE name LIKE ? OR model LIKE ?", (query, query), fetch=True)
    await state.finish()
    if not rows:
        await message.answer("📭 Hech narsa topilmadi.")
        return
    kb = InlineKeyboardMarkup()
    for r in rows:
        kb.add(InlineKeyboardButton(f"{r[1]} (ID:{r[0]})", callback_data=f"product_{r[0]}"))
    await message.answer(f"🔎 Topildi: {len(rows)} ta", reply_markup=kb)

# ============= /db - show users and products (admin only) ==============
@dp.message_handler(commands=['db'], commands_prefix='/', user_id=ADMINS)
async def cmd_db(message: types.Message):
    users = db_query("SELECT telegram_id, telegram_name, age FROM users", fetch=True)
    products = db_query("SELECT id, name, price, model, made_in FROM products ORDER BY id DESC", fetch=True)
    text = "📊 <b>USERS</b>:\n"
    for u in users:
        text += f"ID: {u[0]}, Name: {u[1]}, Age: {u[2]}\n"
    text += "\n📦 <b>PRODUCTS</b>:\n"
    for p in products:
        text += f"ID: {p[0]}, {p[1]}, {p[2]}, {p[3]}, {p[4]}\n"
    await message.answer(text, parse_mode='HTML')

# ============= Bot about ==============
@dp.message_handler(lambda m: m.text == "ℹ️ Bot haqida")
async def about_bot(message: types.Message):
    txt = (
        "Sport City Mr - savdo bot\n"
        "Adminlar mahsulot qo'shadi va boshqaradi.\n"
        "Qo'llanish: /add, /products, /search, /edit, /delete, /db"
    )
    await message.answer(txt)

# ============= fallback ==============
@dp.message_handler()
async def fallback(message: types.Message):
    # if user types plain text, suggest commands
    await message.answer("Men buni tushunmadim. Asosiy menyu uchun /start yoki menyadan tugmalarni tanlang.")

# ============= START POLLING ==============
if __name__ == '__main__':
    logger.info('Bot started...')
    executor.start_polling(dp, skip_updates=True)
