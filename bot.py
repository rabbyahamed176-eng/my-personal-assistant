import os
import json
import asyncio
from datetime import datetime, timedelta
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
MONTHLY_GOAL = 5000
DATA_FILE = "data.json"

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ─── DATA MANAGEMENT ─────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"clients": {}, "tasks": [], "income": [], "expenses": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ─── AI HELPER ────────────────────────────────────────────────────────────────
def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini Error: {str(e)}"

# ─── MAIN MENU ────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👥 Clients", callback_data="menu_clients"),
         InlineKeyboardButton("✅ Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("💰 Finance", callback_data="menu_finance"),
         InlineKeyboardButton("🎯 Goal", callback_data="menu_goal")],
        [InlineKeyboardButton("✍️ AI Content", callback_data="menu_content"),
         InlineKeyboardButton("⏰ Reminders", callback_data="menu_reminders")],
    ]
    await update.message.reply_text(
        "🤖 *তোমার Personal Assistant Bot*\n\nকী করতে চাও?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    handlers = {
        "menu_clients": show_clients_menu,
        "menu_tasks": show_tasks_menu,
        "menu_finance": show_finance_menu,
        "menu_goal": show_goal,
        "menu_content": show_content_menu,
        "menu_reminders": show_reminders_menu,
        "clients_list": list_clients,
        "tasks_list": list_tasks,
        "finance_summary": finance_summary,
    }

    if data in handlers:
        await handlers[data](query)
    elif data == "back_main":
        await back_to_main(query)
    elif data.startswith("complete_task_"):
        await complete_task(query, data.replace("complete_task_", ""))

async def back_to_main(query):
    keyboard = [
        [InlineKeyboardButton("👥 Clients", callback_data="menu_clients"),
         InlineKeyboardButton("✅ Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("💰 Finance", callback_data="menu_finance"),
         InlineKeyboardButton("🎯 Goal", callback_data="menu_goal")],
        [InlineKeyboardButton("✍️ AI Content", callback_data="menu_content"),
         InlineKeyboardButton("⏰ Reminders", callback_data="menu_reminders")],
    ]
    await query.edit_message_text(
        "🤖 *তোমার Personal Assistant Bot*\n\nকী করতে চাও?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ─── CLIENTS ──────────────────────────────────────────────────────────────────
async def show_clients_menu(query):
    keyboard = [
        [InlineKeyboardButton("📋 সব Client দেখো", callback_data="clients_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    await query.edit_message_text(
        "👥 *Client Management*\n\n"
        "`/addclient নাম | status | notes`\n"
        "`/followup নাম | message`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def list_clients(query):
    db = load_data()
    clients = db.get("clients", {})
    if not clients:
        text = "👥 কোনো client নেই।\n\n`/addclient নাম | active | notes` দিয়ে যোগ করো"
    else:
        text = "👥 *আমার Clients:*\n\n"
        for name, info in clients.items():
            emoji = "🟢" if info.get("status") == "active" else "🔴" if info.get("status") == "pending" else "🟡"
            text += f"{emoji} *{name}* — {info.get('status', '?')}\n"
            if info.get("notes"):
                text += f"   📝 {info.get('notes')}\n"
            followups = info.get("followup", [])
            if followups:
                text += f"   📞 Last: {followups[-1]['date']} — {followups[-1]['note']}\n"
            text += "\n"
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_clients")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def add_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/addclient নাম | status | notes`\n"
            "Example: `/addclient Rahman Bhai | active | Logo project`",
            parse_mode="Markdown"
        )
        return
    parts = " ".join(context.args).split("|")
    name = parts[0].strip()
    status = parts[1].strip() if len(parts) > 1 else "new"
    notes = parts[2].strip() if len(parts) > 2 else ""
    db = load_data()
    db["clients"][name] = {
        "status": status, "notes": notes,
        "added": datetime.now().strftime("%Y-%m-%d"), "followup": []
    }
    save_data(db)
    await update.message.reply_text(f"✅ *{name}* যোগ হয়েছে! Status: {status}", parse_mode="Markdown")

async def followup_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/followup নাম | message`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    name = parts[0].strip()
    message = parts[1].strip() if len(parts) > 1 else "Follow up"
    db = load_data()
    if name in db["clients"]:
        db["clients"][name].setdefault("followup", []).append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "note": message
        })
        save_data(db)
        await update.message.reply_text(f"📞 *{name}* এর follow-up log হয়েছে!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ '{name}' নেই। আগে `/addclient` দিয়ে যোগ করো।", parse_mode="Markdown")

# ─── TASKS ────────────────────────────────────────────────────────────────────
async def show_tasks_menu(query):
    keyboard = [
        [InlineKeyboardButton("📋 সব Task দেখো", callback_data="tasks_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    await query.edit_message_text(
        "✅ *Task Manager*\n\n`/addtask কাজ | high/medium/low`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def list_tasks(query):
    db = load_data()
    pending = [t for t in db.get("tasks", []) if not t.get("done")]
    if not pending:
        text = "✅ কোনো pending task নেই! 🎉"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_tasks")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return
    text = "✅ *Pending Tasks:*\n\n"
    keyboard_rows = []
    for i, task in enumerate(pending[:10]):
        emoji = "🔴" if task.get("priority") == "high" else "🟡" if task.get("priority") == "medium" else "🟢"
        text += f"{emoji} {task['title']}\n"
        keyboard_rows.append([InlineKeyboardButton(f"✅ {task['title'][:30]}", callback_data=f"complete_task_{i}")])
    keyboard_rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu_tasks")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode="Markdown")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/addtask কাজের নাম | priority`\n"
            "Example: `/addtask Client proposal | high`",
            parse_mode="Markdown"
        )
        return
    parts = " ".join(context.args).split("|")
    title = parts[0].strip()
    priority = parts[1].strip().lower() if len(parts) > 1 else "medium"
    db = load_data()
    db["tasks"].append({
        "title": title, "priority": priority,
        "done": False, "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    save_data(db)
    emoji = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
    await update.message.reply_text(f"{emoji} Task যোগ: *{title}*", parse_mode="Markdown")

async def complete_task(query, idx_str):
    try:
        db = load_data()
        pending = [t for t in db.get("tasks", []) if not t.get("done")]
        idx = int(idx_str)
        if idx < len(pending):
            title = pending[idx]["title"]
            for t in db["tasks"]:
                if t["title"] == title and not t.get("done"):
                    t["done"] = True
                    t["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    break
            save_data(db)
            await query.edit_message_text(f"🎉 Done: *{title}*\n\nআরো দেখতে /start লেখো", parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"Error: {e}")

# ─── FINANCE ──────────────────────────────────────────────────────────────────
async def show_finance_menu(query):
    keyboard = [
        [InlineKeyboardButton("📊 Summary", callback_data="finance_summary")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")],
    ]
    await query.edit_message_text(
        "💰 *Finance Tracker*\n\n"
        "`/income 500 | Client payment`\n"
        "`/expense 20 | Canva subscription`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/income 500 | Client XYZ`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    try:
        amount = float(parts[0].strip().replace("$", "").replace(",", ""))
        source = parts[1].strip() if len(parts) > 1 else "Unknown"
        db = load_data()
        db["income"].append({"amount": amount, "source": source, "date": datetime.now().strftime("%Y-%m-%d")})
        save_data(db)
        this_month = datetime.now().strftime("%Y-%m")
        monthly = sum(i["amount"] for i in db["income"] if i["date"].startswith(this_month))
        progress = min((monthly / MONTHLY_GOAL) * 100, 100)
        bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
        await update.message.reply_text(
            f"💰 Income: *${amount:.2f}* ({source})\n\n"
            f"🎯 Goal Progress:\n`{bar}` {progress:.1f}%\n"
            f"${monthly:.2f} / $5,000",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Example: `/income 500 | Payment`", parse_mode="Markdown")

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/expense 50 | Software`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    try:
        amount = float(parts[0].strip().replace("$", "").replace(",", ""))
        reason = parts[1].strip() if len(parts) > 1 else "Unknown"
        db = load_data()
        db["expenses"].append({"amount": amount, "reason": reason, "date": datetime.now().strftime("%Y-%m-%d")})
        save_data(db)
        await update.message.reply_text(f"💸 Expense: *${amount:.2f}* ({reason})", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Amount ঠিকমতো দাও।", parse_mode="Markdown")

async def finance_summary(query):
    db = load_data()
    this_month = datetime.now().strftime("%Y-%m")
    income = sum(i["amount"] for i in db["income"] if i["date"].startswith(this_month))
    expense = sum(e["amount"] for e in db["expenses"] if e["date"].startswith(this_month))
    net = income - expense
    progress = min((income / MONTHLY_GOAL) * 100, 100)
    bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    text = (
        f"💰 *এই মাসের Summary*\n\n"
        f"🟢 Income: ${income:.2f}\n"
        f"🔴 Expense: ${expense:.2f}\n"
        f"💵 Net: ${net:.2f}\n\n"
        f"🎯 Goal: `{bar}` {progress:.1f}%\n"
        f"আরো ${max(MONTHLY_GOAL - income, 0):.2f} দরকার"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_finance")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ─── GOAL ─────────────────────────────────────────────────────────────────────
async def show_goal(query):
    db = load_data()
    this_month = datetime.now().strftime("%Y-%m")
    income = sum(i["amount"] for i in db["income"] if i["date"].startswith(this_month))
    progress = min((income / MONTHLY_GOAL) * 100, 100)
    bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    remaining = max(MONTHLY_GOAL - income, 0)
    today = datetime.now()
    last_day = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
    days_left = last_day - today.day
    daily_needed = remaining / max(days_left, 1)

    if progress >= 100:
        motivation = "🎉 *Goal পূরণ! Congratulations!*"
    elif progress >= 75:
        motivation = "💪 Almost there! চালিয়ে যাও!"
    elif progress >= 50:
        motivation = "🔥 Halfway! Focus বাড়াও!"
    else:
        motivation = "⚡ More clients দরকার! Outreach বাড়াও!"

    text = (
        f"🎯 *$5,000 Monthly Goal*\n\n"
        f"`{bar}` {progress:.1f}%\n\n"
        f"✅ Earned: ${income:.2f}\n"
        f"📉 Remaining: ${remaining:.2f}\n"
        f"📅 Days left: {days_left}\n"
        f"💡 Daily needed: ${daily_needed:.2f}\n\n"
        f"{motivation}"
    )
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ─── AI CONTENT ───────────────────────────────────────────────────────────────
async def show_content_menu(query):
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
    await query.edit_message_text(
        "✍️ *AI Content Writer (Gemini - FREE)*\n\n"
        "`/post [topic]` — LinkedIn/Facebook post\n"
        "`/email [purpose]` — Client email\n"
        "`/proposal [service]` — Service proposal\n"
        "`/caption [topic]` — Social media captions\n\n"
        "Example:\n`/post AI automation benefits for small business`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def generate_content(update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: str):
    if not context.args:
        await update.message.reply_text(f"Topic বলো! Example: `/{content_type} your topic`", parse_mode="Markdown")
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text("✍️ Gemini AI লিখছে...")

    prompts = {
        "post": f"Write an engaging LinkedIn/Facebook post about: {topic}\nAdd emojis, make it professional, include a call-to-action. Max 300 words.",
        "email": f"Write a professional client email for: {topic}\nInclude: Subject line, greeting, main content, CTA, sign-off.",
        "proposal": f"Write a service proposal for an AI automation agency about: {topic}\nInclude: Overview, Services, Benefits, Next steps.",
        "caption": f"Write 3 catchy social media captions for: {topic}\nAdd relevant hashtags for each."
    }

    result = ask_gemini(prompts.get(content_type, f"Write professional content about: {topic}"))
    if len(result) > 4000:
        result = result[:3900] + "\n\n_(truncated)_"
    await msg.edit_text(f"✍️ *Generated:*\n\n{result}", parse_mode="Markdown")

async def cmd_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await generate_content(update, context, "post")

async def cmd_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await generate_content(update, context, "email")

async def cmd_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await generate_content(update, context, "proposal")

async def cmd_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await generate_content(update, context, "caption")

# ─── REMINDERS ────────────────────────────────────────────────────────────────
async def show_reminders_menu(query):
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
    await query.edit_message_text(
        "⏰ *Reminders*\n\n"
        "`/remind 30 Call client` — 30 মিনিট পরে\n"
        "`/remind 60 Send invoice` — 1 ঘন্টা পরে\n"
        "`/remind 1440 Weekly report` — 24 ঘন্টা পরে",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/remind 30 Call client`", parse_mode="Markdown")
        return
    try:
        minutes = int(context.args[0])
        text = " ".join(context.args[1:])
        await update.message.reply_text(f"⏰ Set! {minutes} মিনিট পরে remind করবো:\n*{text}*", parse_mode="Markdown")
        await asyncio.sleep(minutes * 60)
        await update.message.reply_text(f"🔔 *REMINDER:*\n\n{text}", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Example: `/remind 30 Call client`", parse_mode="Markdown")

# ─── DAILY SUMMARY ────────────────────────────────────────────────────────────
async def daily_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    this_month = datetime.now().strftime("%Y-%m")
    income = sum(i["amount"] for i in db["income"] if i["date"].startswith(this_month))
    pending_tasks = len([t for t in db.get("tasks", []) if not t.get("done")])
    active_clients = len([c for c, info in db.get("clients", {}).items() if info.get("status") == "active"])
    progress = min((income / MONTHLY_GOAL) * 100, 100)
    bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    remaining = max(MONTHLY_GOAL - income, 0)
    today = datetime.now()
    last_day = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
    days_left = last_day - today.day
    daily_needed = remaining / max(days_left, 1)

    await update.message.reply_text(
        f"📊 *Daily Summary — {today.strftime('%d %b %Y')}*\n\n"
        f"💰 Income this month: ${income:.2f}\n"
        f"`{bar}` {progress:.1f}% of $5k\n\n"
        f"✅ Pending tasks: {pending_tasks}\n"
        f"👥 Active clients: {active_clients}\n\n"
        f"💡 আজকে ${daily_needed:.2f} earn করতে হবে\n\nMenu: /start",
        parse_mode="Markdown"
    )

# ─── AI CHAT ──────────────────────────────────────────────────────────────────
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    msg = await update.message.reply_text("🤔 ভাবছি...")
    prompt = (
        "You are a helpful personal assistant for an AI automation agency owner "
        "trying to earn $5k/month. Help with business, clients, content, productivity. "
        "Be concise and practical. Reply in the same language as the user (Bengali or English).\n\n"
        f"User: {user_msg}"
    )
    result = ask_gemini(prompt)
    if len(result) > 4000:
        result = result[:3900] + "..."
    await msg.edit_text(result)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("summary", daily_summary))
    app.add_handler(CommandHandler("addclient", add_client))
    app.add_handler(CommandHandler("followup", followup_client))
    app.add_handler(CommandHandler("addtask", add_task))
    app.add_handler(CommandHandler("income", add_income))
    app.add_handler(CommandHandler("expense", add_expense))
    app.add_handler(CommandHandler("remind", set_reminder))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("email", cmd_email))
    app.add_handler(CommandHandler("proposal", cmd_proposal))
    app.add_handler(CommandHandler("caption", cmd_caption))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))

    print("🤖 Bot চালু! Telegram এ /start লেখো।")
    app.run_polling()

if __name__ == "__main__":
    main()
