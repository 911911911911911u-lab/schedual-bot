import os
import json
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

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_monday(date):
    day = date.weekday()
    return (date - timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)

def week_key(monday):
    return monday.strftime("week_%Y%m%d")

def get_week_data(monday):
    return load_data().get(week_key(monday), {})

def set_cell(monday, day, hour, field, value):
    data = load_data()
    key = week_key(monday)
    if key not in data: data[key] = {}
    dk = f"d{day}"
    hk = f"h{hour}"
    if dk not in data[key]: data[key][dk] = {}
    if hk not in data[key][dk]: data[key][dk][hk] = {}
    if value:
        data[key][dk][hk][field] = value
    else:
        data[key][dk][hk].pop(field, None)
    save_data(data)

def get_monday_by_week(week):
    today = datetime.now()
    monday = get_monday(today)
    if week == "next":
        monday += timedelta(weeks=1)
    return monday

def build_day_view(week, day_idx):
    monday = get_monday_by_week(week)
    day_date = monday + timedelta(days=day_idx)
    wd = get_week_data(monday)
    day_data = wd.get(f"d{day_idx}", {})

    today = datetime.now()
    is_today = day_date.date() == today.date()
    week_label = "Цей тиждень" if week == "this" else "Наступний тиждень"

    header = f"{'👉 ' if is_today else ''}📅 {DAY_FULL[day_idx]}, {day_date.strftime('%d.%m')}\n{week_label}\n\n"
    lines = [header]

    for hi in range(10):
        cell = day_data.get(f"h{hi}", {})
        r = cell.get("r", "")
        p = cell.get("p", "")

        r_str = f"🔴 {r}" if r else "⬜ вільно"
        p_str = f"🔴 {p}" if p else "⬜ вільно"

        lines.append(
            f"🕐 {HOURS[hi]}\n"
            f"  👤 Відп.: {r_str}\n"
            f"  👥 Напарник: {p_str}\n"
        )

    text = "\n".join(lines)

    # Клавіатура
    buttons = []
    for hi in range(10):
        cell = day_data.get(f"h{hi}", {})
        r = cell.get("r", "")
        p = cell.get("p", "")
        row = []

        if r:
            row.append(InlineKeyboardButton(
                f"✕ 🔴{r[:10]} (відп.)",
                callback_data=f"del|{week}|{day_idx}|{hi}|r"
            ))
        else:
            row.append(InlineKeyboardButton(
                f"✅ + Відп. {9+hi}:00",
                callback_data=f"add|{week}|{day_idx}|{hi}|r"
            ))

        if p:
            row.append(InlineKeyboardButton(
                f"✕ 🔴{p[:10]} (нап.)",
                callback_data=f"del|{week}|{day_idx}|{hi}|p"
            ))
        else:
            row.append(InlineKeyboardButton(
                f"✅ + Напарник {9+hi}:00",
                callback_data=f"add|{week}|{day_idx}|{hi}|p"
            ))

        buttons.append(row)

    # Навігація
    nav = []
    if day_idx > 0:
        nav.append(InlineKeyboardButton(f"◀ {DAY_SHORT[day_idx-1]}", callback_data=f"day|{week}|{day_idx-1}"))
    else:
        nav.append(InlineKeyboardButton("　", callback_data="noop"))

    if day_idx < 6:
        nav.append(InlineKeyboardButton(f"{DAY_SHORT[day_idx+1]} ▶", callback_data=f"day|{week}|{day_idx+1}"))
    else:
        nav.append(InlineKeyboardButton("　", callback_data="noop"))

    buttons.append(nav)

    if week == "this":
        buttons.append([InlineKeyboardButton("📆 Наступний тиждень →", callback_data=f"day|next|{day_idx}")])
    else:
        buttons.append([InlineKeyboardButton("← 📅 Цей тиждень", callback_data=f"day|this|{day_idx}")])

    buttons.append([InlineKeyboardButton("🏠 Меню", callback_data="main")])

    return text, InlineKeyboardMarkup(buttons)

def main_kb():
    di = datetime.now().weekday()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Відкрити графік (цей тиждень)", callback_data=f"day|this|{di}")],
        [InlineKeyboardButton("📆 Наступний тиждень", callback_data="day|next|0")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привіт, {name}! 👋\n\n"
        f"Я бот для графіку служіння зі стендом.\n"
        f"🔴 — зайнято   ⬜ — вільно   ✅ — записатись   ✕ — видалити",
        reply_markup=main_kb()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "noop":
        return

    if d == "main":
        await q.edit_message_text("Оберіть дію:", reply_markup=main_kb())
        return

    parts = d.split("|")

    if parts[0] == "day":
        _, week, day = parts
        text, kb = build_day_view(week, int(day))
        await q.edit_message_text(text, reply_markup=kb)
        return

    if parts[0] == "del":
        _, week, day, hour, field = parts
        monday = get_monday_by_week(week)
        set_cell(monday, int(day), int(hour), field, "")
        text, kb = build_day_view(week, int(day))
        await q.edit_message_text(text, reply_markup=kb)
        return

    if parts[0] == "add":
        _, week, day, hour, field = parts
        field_name = "відповідального" if field == "r" else "напарника"
        context.user_data["pending"] = {
            "week": week, "day": int(day),
            "hour": int(hour), "field": field
        }
        day_i = int(day)
        monday = get_monday_by_week(week)
        day_date = (monday + timedelta(days=day_i)).strftime("%d.%m")
        await q.edit_message_text(
            f"✏️ Введіть прізвище {field_name}:\n"
            f"📅 {DAY_FULL[day_i]}, {day_date}\n"
            f"🕐 {HOURS[int(hour)]}\n\n"
            f"Просто напишіть прізвище у чат:"
        )
        return

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending")
    if not pending:
        await update.message.reply_text("Оберіть дію:", reply_markup=main_kb())
        return

    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Введіть коректне прізвище (мінімум 2 символи):")
        return

    week = pending["week"]
    day = pending["day"]
    hour = pending["hour"]
    field = pending["field"]
    monday = get_monday_by_week(week)
    set_cell(monday, day, hour, field, name)
    context.user_data.pop("pending", None)

    field_name = "Відповідальний" if field == "r" else "Напарник"
    text, kb = build_day_view(week, day)
    await update.message.reply_text(
        f"✅ {field_name}: 🔴 {name} — записано!\n\n" + text,
        reply_markup=kb
    )

async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    di = datetime.now().weekday()
    text, kb = build_day_view("this", di)
    await update.message.reply_text(text, reply_markup=kb)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
