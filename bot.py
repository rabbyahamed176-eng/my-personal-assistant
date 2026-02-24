import os
import json
import logging
from datetime import datetime, timedelta
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackQueryHandler,
    Filters, CallbackContext
)

logging.basicConfig(level=logging.INFO)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MONTHLY_GOAL = 5000
DATA_FILE = "data.json"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── DATA ─────────────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"clients": {}, "tasks": [], "income": [], "expenses": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Error: {str(e)}"

def goal_bar(income):
    progress = min((income / MONTHLY_GOAL) * 100, 100)
    bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    return bar, progress

# ─── MAIN MENU ────────────────────────────────────────────────────────────────
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("👥 Clients", callback_data="menu_clients"),
         InlineKeyboardButton("✅ Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("💰 Finance", callback_data="menu_finance"),
         InlineKeyboardButton("🎯 Goal", callback_data="menu_goal")],
        [InlineKeyboardButton("✍️ AI Content", callback_data="menu_content"),
         InlineKeyboardButton("⏰ Reminders", callback_data="menu_reminders")],
    ]
    update.message.reply_text(
        "🤖 *তোমার Personal Assistant Bot*\n\nকী করতে চাও?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ─── BUTTONS ──────────────────────────────────────────────────────────────────
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data

    main_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Clients", callback_data="menu_clients"),
         InlineKeyboardButton("✅ Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("💰 Finance", callback_data="menu_finance"),
         InlineKeyboardButton("🎯 Goal", callback_data="menu_goal")],
        [InlineKeyboardButton("✍️ AI Content", callback_data="menu_content"),
         InlineKeyboardButton("⏰ Reminders", callback_data="menu_reminders")],
    ])
    back_kb = lambda cb: InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=cb)]])

    if data == "back_main":
        query.edit_message_text("🤖 *তোমার Personal Assistant Bot*\n\nকী করতে চাও?",
                                reply_markup=main_kb, parse_mode="Markdown")

    elif data == "menu_clients":
        query.edit_message_text(
            "👥 *Client Management*\n\n`/addclient নাম | status | notes`\n`/followup নাম | message`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 সব Client", callback_data="clients_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ]), parse_mode="Markdown")

    elif data == "clients_list":
        db = load_data()
        clients = db.get("clients", {})
        if not clients:
            text = "👥 কোনো client নেই।\n\n`/addclient নাম | active | notes`"
        else:
            text = "👥 *আমার Clients:*\n\n"
            for name, info in clients.items():
                e = "🟢" if info.get("status") == "active" else "🔴" if info.get("status") == "pending" else "🟡"
                text += f"{e} *{name}* — {info.get('status','?')}\n"
                if info.get("notes"): text += f"   📝 {info['notes']}\n"
                fu = info.get("followup", [])
                if fu: text += f"   📞 Last: {fu[-1]['date']} — {fu[-1]['note']}\n"
                text += "\n"
        query.edit_message_text(text, reply_markup=back_kb("menu_clients"), parse_mode="Markdown")

    elif data == "menu_tasks":
        query.edit_message_text(
            "✅ *Task Manager*\n\n`/addtask কাজ | high/medium/low`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 সব Task", callback_data="tasks_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ]), parse_mode="Markdown")

    elif data == "tasks_list":
        db = load_data()
        pending = [t for t in db.get("tasks", []) if not t.get("done")]
        if not pending:
            query.edit_message_text("✅ কোনো pending task নেই! 🎉",
                                    reply_markup=back_kb("menu_tasks"), parse_mode="Markdown")
        else:
            text = "✅ *Pending Tasks:*\n\n"
            rows = []
            for i, t in enumerate(pending[:10]):
                e = "🔴" if t.get("priority") == "high" else "🟡" if t.get("priority") == "medium" else "🟢"
                text += f"{e} {t['title']}\n"
                rows.append([InlineKeyboardButton(f"✅ {t['title'][:30]}", callback_data=f"done_{i}")])
            rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu_tasks")])
            query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")

    elif data.startswith("done_"):
        idx = int(data.replace("done_", ""))
        db = load_data()
        pending = [t for t in db.get("tasks", []) if not t.get("done")]
        if idx < len(pending):
            title = pending[idx]["title"]
            for t in db["tasks"]:
                if t["title"] == title and not t.get("done"):
                    t["done"] = True
                    break
            save_data(db)
            query.edit_message_text(f"🎉 Done: *{title}*\n\n/start দিয়ে menu দেখো", parse_mode="Markdown")

    elif data == "menu_finance":
        query.edit_message_text(
            "💰 *Finance*\n\n`/income 500 | Client payment`\n`/expense 20 | Canva`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Summary", callback_data="finance_summary")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ]), parse_mode="Markdown")

    elif data == "finance_summary":
        db = load_data()
        m = datetime.now().strftime("%Y-%m")
        inc = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
        exp = sum(e["amount"] for e in db["expenses"] if e["date"].startswith(m))
        bar, prog = goal_bar(inc)
        query.edit_message_text(
            f"💰 *এই মাসের Summary*\n\n🟢 Income: ${inc:.2f}\n🔴 Expense: ${exp:.2f}\n💵 Net: ${inc-exp:.2f}\n\n"
            f"🎯 `{bar}` {prog:.1f}%\nআরো ${max(MONTHLY_GOAL-inc,0):.2f} দরকার",
            reply_markup=back_kb("menu_finance"), parse_mode="Markdown")

    elif data == "menu_goal":
        db = load_data()
        m = datetime.now().strftime("%Y-%m")
        inc = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
        bar, prog = goal_bar(inc)
        remaining = max(MONTHLY_GOAL - inc, 0)
        today = datetime.now()
        last_day = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        days_left = last_day - today.day
        daily = remaining / max(days_left, 1)
        if prog >= 100: mot = "🎉 Goal পূরণ!"
        elif prog >= 75: mot = "💪 Almost there!"
        elif prog >= 50: mot = "🔥 Halfway! Focus করো!"
        else: mot = "⚡ Outreach বাড়াও!"
        query.edit_message_text(
            f"🎯 *$5,000 Monthly Goal*\n\n`{bar}` {prog:.1f}%\n\n✅ Earned: ${inc:.2f}\n📉 Remaining: ${remaining:.2f}\n"
            f"📅 Days left: {days_left}\n💡 Daily needed: ${daily:.2f}\n\n{mot}",
            reply_markup=back_kb("back_main"), parse_mode="Markdown")

    elif data == "menu_content":
        query.edit_message_text(
            "✍️ *AI Content (Gemini FREE)*\n\n`/post topic`\n`/email purpose`\n`/proposal service`\n`/caption topic`",
            reply_markup=back_kb("back_main"), parse_mode="Markdown")

    elif data == "menu_reminders":
        query.edit_message_text(
            "⏰ *Reminders*\n\n`/remind 30 Call client`\n`/remind 60 Send invoice`",
            reply_markup=back_kb("back_main"), parse_mode="Markdown")

# ─── COMMANDS ─────────────────────────────────────────────────────────────────
def add_client(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: `/addclient নাম | active | notes`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    name = parts[0].strip()
    status = parts[1].strip() if len(parts) > 1 else "new"
    notes = parts[2].strip() if len(parts) > 2 else ""
    db = load_data()
    db["clients"][name] = {"status": status, "notes": notes, "added": datetime.now().strftime("%Y-%m-%d"), "followup": []}
    save_data(db)
    update.message.reply_text(f"✅ *{name}* যোগ হয়েছে!", parse_mode="Markdown")

def followup(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: `/followup নাম | message`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    name = parts[0].strip()
    msg = parts[1].strip() if len(parts) > 1 else "Follow up"
    db = load_data()
    if name in db["clients"]:
        db["clients"][name].setdefault("followup", []).append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "note": msg})
        save_data(db)
        update.message.reply_text(f"📞 *{name}* follow-up log হয়েছে!", parse_mode="Markdown")
    else:
        update.message.reply_text(f"❌ '{name}' নেই।", parse_mode="Markdown")

def add_task(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: `/addtask কাজ | high`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    title = parts[0].strip()
    priority = parts[1].strip().lower() if len(parts) > 1 else "medium"
    db = load_data()
    db["tasks"].append({"title": title, "priority": priority, "done": False, "created": datetime.now().strftime("%Y-%m-%d %H:%M")})
    save_data(db)
    e = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
    update.message.reply_text(f"{e} Task যোগ: *{title}*", parse_mode="Markdown")

def add_income(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: `/income 500 | Client`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    try:
        amount = float(parts[0].strip().replace("$", "").replace(",", ""))
        source = parts[1].strip() if len(parts) > 1 else "Unknown"
        db = load_data()
        db["income"].append({"amount": amount, "source": source, "date": datetime.now().strftime("%Y-%m-%d")})
        save_data(db)
        m = datetime.now().strftime("%Y-%m")
        monthly = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
        bar, prog = goal_bar(monthly)
        update.message.reply_text(
            f"💰 Income: *${amount:.2f}* ({source})\n\n🎯 `{bar}` {prog:.1f}%\n${monthly:.2f} / $5,000",
            parse_mode="Markdown")
    except:
        update.message.reply_text("❌ Example: `/income 500 | Payment`", parse_mode="Markdown")

def add_expense(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("Usage: `/expense 50 | Software`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    try:
        amount = float(parts[0].strip().replace("$", "").replace(",", ""))
        reason = parts[1].strip() if len(parts) > 1 else "Unknown"
        db = load_data()
        db["expenses"].append({"amount": amount, "reason": reason, "date": datetime.now().strftime("%Y-%m-%d")})
        save_data(db)
        update.message.reply_text(f"💸 Expense: *${amount:.2f}* ({reason})", parse_mode="Markdown")
    except:
        update.message.reply_text("❌ Amount ঠিকমতো দাও।", parse_mode="Markdown")

def remind(update: Update, context: CallbackContext):
    update.message.reply_text(
        "⏰ Reminder feature এর জন্য `/remind 30 Call client` লেখো।\n\n"
        "⚠️ Note: Bot restart হলে reminder cancel হয়ে যায়।", parse_mode="Markdown")

def generate(update: Update, context: CallbackContext, ctype: str):
    if not context.args:
        update.message.reply_text(f"Topic দাও! Example: `/{ctype} your topic`", parse_mode="Markdown")
        return
    topic = " ".join(context.args)
    msg = update.message.reply_text("✍️ Gemini লিখছে...")
    prompts = {
        "post": f"Write an engaging LinkedIn/Facebook post about: {topic}. Add emojis, CTA. Max 300 words.",
        "email": f"Write a professional client email for: {topic}. Include subject line.",
        "proposal": f"Write a service proposal for AI automation agency about: {topic}.",
        "caption": f"Write 3 social media captions for: {topic}. Add hashtags."
    }
    result = ask_gemini(prompts.get(ctype, f"Write about: {topic}"))
    if len(result) > 4000: result = result[:3900] + "..."
    msg.edit_text(f"✍️ *Generated:*\n\n{result}", parse_mode="Markdown")

def cmd_post(update, context): generate(update, context, "post")
def cmd_email(update, context): generate(update, context, "email")
def cmd_proposal(update, context): generate(update, context, "proposal")
def cmd_caption(update, context): generate(update, context, "caption")

def summary(update: Update, context: CallbackContext):
    db = load_data()
    m = datetime.now().strftime("%Y-%m")
    inc = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
    pending = len([t for t in db.get("tasks", []) if not t.get("done")])
    active = len([c for c, info in db.get("clients", {}).items() if info.get("status") == "active"])
    bar, prog = goal_bar(inc)
    remaining = max(MONTHLY_GOAL - inc, 0)
    today = datetime.now()
    last_day = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
    days_left = last_day - today.day
    daily = remaining / max(days_left, 1)
    update.message.reply_text(
        f"📊 *Daily Summary — {today.strftime('%d %b %Y')}*\n\n"
        f"💰 Income: ${inc:.2f}\n`{bar}` {prog:.1f}%\n\n"
        f"✅ Pending tasks: {pending}\n👥 Active clients: {active}\n\n"
        f"💡 আজকে ${daily:.2f} earn করতে হবে\n\nMenu: /start",
        parse_mode="Markdown")

def ai_chat(update: Update, context: CallbackContext):
    msg = update.message.reply_text("🤔 ভাবছি...")
    prompt = (
        "You are a helpful assistant for an AI automation agency owner trying to earn $5k/month. "
        "Be concise and practical. Reply in the same language as the user (Bengali or English).\n\n"
        f"User: {update.message.text}"
    )
    result = ask_gemini(prompt)
    if len(result) > 4000: result = result[:3900] + "..."
    msg.edit_text(result)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("menu", start))
    dp.add_handler(CommandHandler("summary", summary))
    dp.add_handler(CommandHandler("addclient", add_client))
    dp.add_handler(CommandHandler("followup", followup))
    dp.add_handler(CommandHandler("addtask", add_task))
    dp.add_handler(CommandHandler("income", add_income))
    dp.add_handler(CommandHandler("expense", add_expense))
    dp.add_handler(CommandHandler("remind", remind))
    dp.add_handler(CommandHandler("post", cmd_post))
    dp.add_handler(CommandHandler("email", cmd_email))
    dp.add_handler(CommandHandler("proposal", cmd_proposal))
    dp.add_handler(CommandHandler("caption", cmd_caption))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, ai_chat))

    print("🤖 Bot চালু!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
