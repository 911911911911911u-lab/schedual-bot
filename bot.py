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

HOURS = [f"{9+i}:00\u2013{10+i}:00" for i in range(10)]
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
    data = load_data()
    return data.get(week_key(monday), {})

def set_cell(monday, day, hour, field, value):
    data = load_data()
    key = week_key(monday)
    if key not in data:
        data[key] = {}
    dk = f"d{day}"
    hk = f"h{hour}"
    if dk not in data[key]:
        data[key][dk] = {}
    if hk not in data[key][dk]:
        data[key][dk][hk] = {}
    if value:
        data[key][dk][hk][field] = value
    else:
        data[key][dk][hk].pop(field, None)
    save_data(data)

def format_schedule(monday, week_label):
    wd = get_week_data(monday)
    today_str = datetime.now().strftime("%d.%m")
    end = monday + timedelta(days=6)
    lines = [
        f"📋 Графік служіння — {week_label}",
        f"{monday.strftime('%d.%m')} – {end.strftime('%d.%m')}",
        ""
    ]
    for di in range(7):
        day_date = monday + timedelta(days=di)
        date_str = day_date.strftime("%d.%m")
        prefix = "👉 " if date_str == today_str else ""
        lines.append(f"{prefix}{DAY_SHORT[di]} {date_str} — {DAY_FULL[di]}")
        day_data = wd.get(f"d{di}", {})
        has = False
        for hi in range(10):
            cell = day_data.get(f"h{hi}", {})
            r = cell.get("r", "")
            p = cell.get("p", "")
            if r or p:
                has = True
                lines.append(f"  {HOURS[hi]}:  {r or '___'} / {p or '___'}")
        if not has:
            lines.append("  — порожньо —")
        lines.append("")
    return "\n".join(lines)

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Цей тиждень", callback_data="view_this"),
         InlineKeyboardButton("📆 Наступний", callback_data="view_next")],
        [InlineKeyboardButton("✏️ Записатись", callback_data="act_signup"),
         InlineKeyboardButton("❌ Відписатись", callback_data="act_signoff")],
    ])

def week_kb(action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Цей тиждень", callback_data=f"{action}|this"),
         InlineKeyboardButton("Наступний", callback_data=f"{action}|next")],
        [InlineKeyboardButton("« Назад", callback_data="main")],
    ])

def day_kb(action, week):
    today = datetime.now()
    monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
    buttons = []
    row = []
    for di in range(7):
        d = monday + timedelta(days=di)
        row.append(InlineKeyboardButton(
            f"{DAY_SHORT[di]} {d.strftime('%d.%m')}",
            callback_data=f"{action}|{week}|{di}"
        ))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("« Назад", callback_data=f"act_{action}")])
    return InlineKeyboardMarkup(buttons)

def hour_kb(action, week, day):
    buttons = []
    row = []
    for hi in range(10):
        row.append(InlineKeyboardButton(
            HOURS[hi],
            callback_data=f"{action}|{week}|{day}|{hi}"
        ))
        if len(row) == 2:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton("« Назад", callback_data=f"{action}|{week}")])
    return InlineKeyboardMarkup(buttons)

def field_kb(action, week, day, hour):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Відповідальний", callback_data=f"{action}|{week}|{day}|{hour}|r"),
         InlineKeyboardButton("👥 Напарник",       callback_data=f"{action}|{week}|{day}|{hour}|p")],
        [InlineKeyboardButton("« Назад", callback_data=f"{action}|{week}|{day}")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привіт, {name}! 👋\nЯ бот для графіку служіння зі стендом.\nОберіть дію:",
        reply_markup=main_kb()
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    parts = d.split("|")

    # Головне меню
    if d == "main":
        await q.edit_message_text("Оберіть дію:", reply_markup=main_kb())
        return

    # Перегляд
    if d == "view_this":
        monday = get_monday(datetime.now())
        await q.edit_message_text(
            format_schedule(monday, "Цей тиждень"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="main")]])
        )
        return

    if d == "view_next":
        monday = get_monday(datetime.now()) + timedelta(weeks=1)
        await q.edit_message_text(
            format_schedule(monday, "Наступний тиждень"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data="main")]])
        )
        return

    # Вибір дії
    if d == "act_signup":
        await q.edit_message_text("✏️ Записатись\nОберіть тиждень:", reply_markup=week_kb("signup"))
        return

    if d == "act_signoff":
        await q.edit_message_text("❌ Відписатись\nОберіть тиждень:", reply_markup=week_kb("signoff"))
        return

    # signup|week або signoff|week
    if len(parts) == 2:
        action, week = parts
        if action in ("signup", "signoff"):
            today = datetime.now()
            monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
            await q.edit_message_text(
                "📅 Оберіть день:",
                reply_markup=day_kb(action, week)
            )
            return

    # signup|week|day або signoff|week|day
    if len(parts) == 3:
        action, week, day = parts
        if action in ("signup", "signoff"):
            await q.edit_message_text(
                f"🕐 Оберіть час ({DAY_FULL[int(day)]}):",
                reply_markup=hour_kb(action, week, int(day))
            )
            return

    # signup|week|day|hour або signoff|week|day|hour
    if len(parts) == 4:
        action, week, day, hour = parts
        if action in ("signup", "signoff"):
            await q.edit_message_text(
                f"Оберіть роль:\n{DAY_FULL[int(day)]}, {HOURS[int(hour)]}",
                reply_markup=field_kb(action, week, int(day), int(hour))
            )
            return

    # signup|week|day|hour|field
    if len(parts) == 5:
        action, week, day, hour, field = parts
        day = int(day); hour = int(hour)
        today = datetime.now()
        monday = get_monday(today) if week == "this" else get_monday(today) + timedelta(weeks=1)
        field_name = "Відповідальний" if field == "r" else "Напарник"

        if action == "signoff":
            set_cell(monday, day, hour, field, "")
            await q.edit_message_text(
                f"✅ Запис видалено!\n{DAY_FULL[day]}, {HOURS[hour]}, {field_name}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Меню", callback_data="main")]])
            )
            return

        if action == "signup":
            context.user_data["pending"] = {
                "week": week, "day": day, "hour": hour, "field": field,
                "monday": monday.isoformat()
            }
            await q.edit_message_text(
                f"✏️ Введіть своє прізвище:\n{DAY_FULL[day]}, {HOURS[hour]}, {field_name}\n\nПросто напишіть прізвище:"
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

    day = pending["day"]; hour = pending["hour"]; field = pending["field"]
    monday = datetime.fromisoformat(pending["monday"])
    field_name = "Відповідальний" if field == "r" else "Напарник"
    set_cell(monday, day, hour, field, name)
    context.user_data.pop("pending", None)

    await update.message.reply_text(
        f"✅ Записано!\n{DAY_FULL[day]}, {HOURS[hour]}\n{field_name}: {name}",
        reply_markup=main_kb()
    )

async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    monday = get_monday(datetime.now())
    await update.message.reply_text(
        format_schedule(monday, "Цей тиждень"),
        reply_markup=main_kb()
    )

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
