import os
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

TOKEN = os.environ.get("BOT_TOKEN", "8810579160:AAF-YCvLwffW2Tx7dL-PuJ_PyVEhNbknIW0")
DATA_FILE = "schedule_data.json"

HOURS = [f"{9+i}:00–{10+i}:00" for i in range(10)]
DAY_SHORT = ["Пн","Вт","Ср","Чт","Пт","Сб","Нд"]
DAY_FULL  = ["Понеділок","Вівторок","Середа","Четвер","П'ятниця","Субота","Неділя"]

# ── Data helpers ──
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_monday(date):
    day = date.weekday()  # 0=Mon
    return (date - timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)

def week_key(monday):
    return monday.strftime("week_%Y%m%d")

def auto_reset():
    """Скидає поточний тиждень якщо він вже закінчився"""
    data = load_data()
    today = datetime.now()
    this_monday = get_monday(today)
    this_sunday = this_monday + timedelta(days=6, hours=23, minutes=59)
    key = week_key(this_monday)
    # Якщо минуло більше тижня — очищаємо
    if today > this_sunday and key in data:
        del data[key]
        save_data(data)

def get_week_data(monday):
    auto_reset()
    data = load_data()
    key = week_key(monday)
    return data.get(key, {})

def set_cell(monday, day, hour, field, value):
    data = load_data()
    key = week_key(monday)
    if key not in data:
        data[key] = {}
    if f"d{day}" not in data[key]:
        data[key][f"d{day}"] = {}
    if f"h{hour}" not in data[key][f"d{day}"]:
        data[key][f"d{day}"][f"h{hour}"] = {}
    if value:
        data[key][f"d{day}"][f"h{hour}"][field] = value
    else:
        data[key][f"d{day}"][f"h{hour}"].pop(field, None)
    save_data(data)

# ── Formatters ──
def format_schedule(monday, week_label):
    wd = get_week_data(monday)
    today = datetime.now()
    today_str = today.strftime("%d.%m")

    lines = [f"📋 *Графік служіння — {week_label}*"]
    lines.append(f"_{monday.strftime('%d.%m')} – {(monday+timedelta(days=6)).strftime('%d.%m')}_\n")

    for di in range(7):
        day_date = monday + timedelta(days=di)
        date_str = day_date.strftime("%d.%m")
        is_today = date_str == today_str
        prefix = "👉 " if is_today else ""
        lines.append(f"{prefix}*{DAY_SHORT[di]} {date_str} — {DAY_FULL[di]}*")

        day_data = wd.get(f"d{di}", {})
        has_entries = False
        for hi in range(10):
            cell = day_data.get(f"h{hi}", {})
            r = cell.get("r", "")
            p = cell.get("p", "")
            if r or p:
                has_entries = True
                r_str = r if r else "\_\_\_"
                p_str = p if p else "\_\_\_"
                lines.append(f"  `{HOURS[hi]}` {r_str} / {p_str}")
        if not has_entries:
            lines.append("  _— порожньо —_")
        lines.append("")

    return "\n".join(lines)

def make_main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📅 Цей тиждень", callback_data="view_this"),
            InlineKeyboardButton("📆 Наступний", callback_data="view_next"),
        ],
        [
            InlineKeyboardButton("✏️ Записатись", callback_data="sign_up"),
            InlineKeyboardButton("❌ Відписатись", callback_data="sign_off"),
        ],
        [
            InlineKeyboardButton("🗑 Очистити запис", callback_data="clear_cell"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def make_week_keyboard(action):
    keyboard = [
        [
            InlineKeyboardButton("Цей тиждень", callback_data=f"{action}_this"),
            InlineKeyboardButton("Наступний", callback_data=f"{action}_next"),
        ],
        [InlineKeyboardButton("« Назад", callback_data="main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def make_day_keyboard(action, week):
    today = datetime.now()
    monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
    buttons = []
    row = []
    for di in range(7):
        day_date = monday + timedelta(days=di)
        row.append(InlineKeyboardButton(
            f"{DAY_SHORT[di]} {day_date.strftime('%d.%m')}",
            callback_data=f"{action}_{week}_d{di}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("« Назад", callback_data=f"week_{action}")])
    return InlineKeyboardMarkup(buttons)

def make_hour_keyboard(action, week, day):
    buttons = []
    row = []
    for hi in range(10):
        row.append(InlineKeyboardButton(
            HOURS[hi], callback_data=f"{action}_{week}_d{day}_h{hi}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("« Назад", callback_data=f"day_{action}_{week}")])
    return InlineKeyboardMarkup(buttons)

def make_field_keyboard(action, week, day, hour):
    keyboard = [
        [
            InlineKeyboardButton("👤 Відповідальний", callback_data=f"{action}_{week}_d{day}_h{hour}_r"),
            InlineKeyboardButton("👥 Напарник", callback_data=f"{action}_{week}_d{day}_h{hour}_p"),
        ],
        [InlineKeyboardButton("« Назад", callback_data=f"hour_{action}_{week}_d{day}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ── Handlers ──
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привіт, *{name}*\\! 👋\n\nЯ бот для графіку служіння зі стендом\\.\nОбери дію:",
        parse_mode="MarkdownV2",
        reply_markup=make_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Головне меню ──
    if data == "main":
        await query.edit_message_text(
            "Оберіть дію:",
            reply_markup=make_main_keyboard()
        )
        return

    # ── Перегляд ──
    if data == "view_this":
        today = datetime.now()
        monday = get_monday(today)
        text = format_schedule(monday, "Цей тиждень")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="main")]])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    if data == "view_next":
        today = datetime.now()
        monday = get_monday(today) + timedelta(weeks=1)
        text = format_schedule(monday, "Наступний тиждень")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="main")]])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        return

    # ── Записатись ──
    if data == "sign_up":
        await query.edit_message_text(
            "✏️ *Записатись*\nОберіть тиждень:",
            parse_mode="Markdown",
            reply_markup=make_week_keyboard("signup")
        )
        return

    if data == "week_signup":
        await query.edit_message_text("Оберіть тиждень:", reply_markup=make_week_keyboard("signup"))
        return

    if data in ("signup_this", "signup_next"):
        week = data.split("_")[1]
        await query.edit_message_text(
            "📅 Оберіть день:",
            reply_markup=make_day_keyboard("signup", week)
        )
        return

    if data.startswith("day_signup_"):
        week = data.split("_")[2]
        await query.edit_message_text(
            "🕐 Оберіть час:",
            reply_markup=make_day_keyboard("signup", week)
        )
        return

    if data.startswith("signup_") and "_d" in data and "_h" not in data:
        parts = data.split("_")
        week = parts[1]
        day = parts[2][1:]
        await query.edit_message_text(
            f"🕐 Оберіть часовий інтервал ({DAY_FULL[int(day)]}):",
            reply_markup=make_hour_keyboard("signup", week, day)
        )
        return

    if data.startswith("hour_signup_"):
        parts = data.split("_")
        week = parts[2]
        day = parts[3][1:]
        await query.edit_message_text(
            "🕐 Оберіть час:",
            reply_markup=make_hour_keyboard("signup", week, day)
        )
        return

    if data.startswith("signup_") and "_d" in data and "_h" in data and data.count("_") == 4:
        parts = data.split("_")
        week = parts[1]
        day = int(parts[2][1:])
        hour = int(parts[3][1:])
        await query.edit_message_text(
            f"👤 Оберіть роль для *{DAY_FULL[day]}* о *{HOURS[hour]}*:",
            parse_mode="Markdown",
            reply_markup=make_field_keyboard("signup", week, day, hour)
        )
        return

    if data.startswith("signup_") and ("_r" in data or "_p" in data):
        parts = data.split("_")
        week = parts[1]
        day = int(parts[2][1:])
        hour = int(parts[3][1:])
        field = parts[4]
        field_name = "Відповідальний" if field == "r" else "Напарник"
        # Зберігаємо контекст
        context.user_data["pending"] = {
            "week": week, "day": day, "hour": hour, "field": field
        }
        await query.edit_message_text(
            f"✏️ Введіть своє *прізвище* для запису:\n"
            f"_{DAY_FULL[day]}, {HOURS[hour]}, {field_name}_\n\n"
            f"Просто напишіть прізвище у чат:",
            parse_mode="Markdown"
        )
        return

    # ── Відписатись (очистити свій запис) ──
    if data == "sign_off":
        await query.edit_message_text(
            "❌ *Відписатись*\nОберіть тиждень:",
            parse_mode="Markdown",
            reply_markup=make_week_keyboard("signoff")
        )
        return

    if data == "week_signoff":
        await query.edit_message_text("Оберіть тиждень:", reply_markup=make_week_keyboard("signoff"))
        return

    if data in ("signoff_this", "signoff_next"):
        week = data.split("_")[1]
        await query.edit_message_text("📅 Оберіть день:", reply_markup=make_day_keyboard("signoff", week))
        return

    if data.startswith("signoff_") and "_d" in data and "_h" not in data:
        parts = data.split("_")
        week = parts[1]
        day = parts[2][1:]
        await query.edit_message_text(
            f"🕐 Оберіть час ({DAY_FULL[int(day)]}):",
            reply_markup=make_hour_keyboard("signoff", week, day)
        )
        return

    if data.startswith("hour_signoff_"):
        parts = data.split("_")
        week = parts[2]
        day = parts[3][1:]
        await query.edit_message_text("🕐 Оберіть час:", reply_markup=make_hour_keyboard("signoff", week, day))
        return

    if data.startswith("signoff_") and "_d" in data and "_h" in data and data.count("_") == 4:
        parts = data.split("_")
        week = parts[1]
        day = int(parts[2][1:])
        hour = int(parts[3][1:])
        await query.edit_message_text(
            f"Яку роль видалити?\n*{DAY_FULL[day]}, {HOURS[hour]}*",
            parse_mode="Markdown",
            reply_markup=make_field_keyboard("signoff", week, day, hour)
        )
        return

    if data.startswith("signoff_") and ("_r" in data or "_p" in data):
        parts = data.split("_")
        week = parts[1]
        day = int(parts[2][1:])
        hour = int(parts[3][1:])
        field = parts[4]
        today = datetime.now()
        monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
        set_cell(monday, day, hour, field, "")
        field_name = "Відповідальний" if field == "r" else "Напарник"
        await query.edit_message_text(
            f"✅ Запис видалено!\n_{DAY_FULL[day]}, {HOURS[hour]}, {field_name}_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Меню", callback_data="main")]])
        )
        return

    # ── Очистити запис (адмін) ──
    if data == "clear_cell":
        await query.edit_message_text(
            "🗑 *Очистити запис*\nОберіть тиждень:",
            parse_mode="Markdown",
            reply_markup=make_week_keyboard("clear")
        )
        return

    if data in ("clear_this", "clear_next"):
        week = data.split("_")[1]
        await query.edit_message_text("📅 Оберіть день:", reply_markup=make_day_keyboard("clear", week))
        return

    if data.startswith("clear_") and "_d" in data and "_h" not in data:
        parts = data.split("_")
        week = parts[1]
        day = parts[2][1:]
        await query.edit_message_text(
            f"🕐 Оберіть час ({DAY_FULL[int(day)]}):",
            reply_markup=make_hour_keyboard("clear", week, day)
        )
        return

    if data.startswith("hour_clear_"):
        parts = data.split("_")
        week = parts[2]
        day = parts[3][1:]
        await query.edit_message_text("🕐 Оберіть час:", reply_markup=make_hour_keyboard("clear", week, day))
        return

    if data.startswith("clear_") and "_d" in data and "_h" in data and data.count("_") == 4:
        parts = data.split("_")
        week = parts[1]
        day = int(parts[2][1:])
        hour = int(parts[3][1:])
        await query.edit_message_text(
            f"Яку роль очистити?\n*{DAY_FULL[day]}, {HOURS[hour]}*",
            parse_mode="Markdown",
            reply_markup=make_field_keyboard("clear", week, day, hour)
        )
        return

    if data.startswith("clear_") and ("_r" in data or "_p" in data):
        parts = data.split("_")
        week = parts[1]
        day = int(parts[2][1:])
        hour = int(parts[3][1:])
        field = parts[4]
        today = datetime.now()
        monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
        set_cell(monday, day, hour, field, "")
        field_name = "Відповідальний" if field == "r" else "Напарник"
        await query.edit_message_text(
            f"🗑 Запис очищено!\n_{DAY_FULL[day]}, {HOURS[hour]}, {field_name}_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Меню", callback_data="main")]])
        )
        return

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending")
    if not pending:
        await update.message.reply_text(
            "Оберіть дію:",
            reply_markup=make_main_keyboard()
        )
        return

    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Введіть коректне прізвище (мінімум 2 символи):")
        return

    week = pending["week"]
    day = pending["day"]
    hour = pending["hour"]
    field = pending["field"]
    field_name = "Відповідальний" if field == "r" else "Напарник"

    today = datetime.now()
    monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
    set_cell(monday, day, hour, field, name)
    context.user_data.pop("pending", None)

    await update.message.reply_text(
        f"✅ *Записано\\!*\n"
        f"_{DAY_FULL[day]}, {HOURS[hour]}_\n"
        f"_{field_name}: {name}_",
        parse_mode="MarkdownV2",
        reply_markup=make_main_keyboard()
    )

async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    monday = get_monday(today)
    text = format_schedule(monday, "Цей тиждень")
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=make_main_keyboard())

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
