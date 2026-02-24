import os
import json
import logging
from datetime import datetime, timedelta
from groq import Groq
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MONTHLY_GOAL = 5000
DATA_FILE = "data.json"

groq_client = Groq(api_key=GROQ_API_KEY)

def ask_ai(prompt, system="You are a helpful assistant for an AI automation agency owner trying to earn $5k/month. Be concise and practical. Reply in Bengali or English based on user's language."):
    try:
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error: {str(e)}"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"clients": {}, "tasks": [], "income": [], "expenses": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_bar(income):
    progress = min((income / MONTHLY_GOAL) * 100, 100)
    bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
    return bar, progress

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Clients", callback_data="menu_clients"),
         InlineKeyboardButton("✅ Tasks", callback_data="menu_tasks")],
        [InlineKeyboardButton("💰 Finance", callback_data="menu_finance"),
         InlineKeyboardButton("🎯 Goal", callback_data="menu_goal")],
        [InlineKeyboardButton("✍️ AI Content", callback_data="menu_content"),
         InlineKeyboardButton("⏰ Reminders", callback_data="menu_reminders")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Chitti - তোমার Personal Assistant*\n\nকী করতে চাও?",
        reply_markup=main_keyboard(), parse_mode="Markdown"
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    back = lambda cb: InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=cb)]])

    if d == "back_main":
        await q.edit_message_text("🤖 *Chitti - তোমার Personal Assistant*\n\nকী করতে চাও?",
                                   reply_markup=main_keyboard(), parse_mode="Markdown")

    elif d == "menu_clients":
        await q.edit_message_text(
            "👥 *Clients*\n\n`/addclient নাম | active | notes`\n`/followup নাম | message`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 সব Client", callback_data="clients_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ]), parse_mode="Markdown")

    elif d == "clients_list":
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
                if fu: text += f"   📞 {fu[-1]['date']} — {fu[-1]['note']}\n"
                text += "\n"
        await q.edit_message_text(text, reply_markup=back("menu_clients"), parse_mode="Markdown")

    elif d == "menu_tasks":
        await q.edit_message_text(
            "✅ *Tasks*\n\n`/addtask কাজ | high/medium/low`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 সব Task", callback_data="tasks_list")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ]), parse_mode="Markdown")

    elif d == "tasks_list":
        db = load_data()
        pending = [t for t in db.get("tasks", []) if not t.get("done")]
        if not pending:
            await q.edit_message_text("✅ কোনো pending task নেই! 🎉",
                                       reply_markup=back("menu_tasks"), parse_mode="Markdown")
        else:
            text = "✅ *Pending Tasks:*\n\n"
            rows = []
            for i, t in enumerate(pending[:10]):
                e = "🔴" if t.get("priority") == "high" else "🟡" if t.get("priority") == "medium" else "🟢"
                text += f"{e} {t['title']}\n"
                rows.append([InlineKeyboardButton(f"✅ {t['title'][:28]}", callback_data=f"done_{i}")])
            rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu_tasks")])
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="Markdown")

    elif d.startswith("done_"):
        idx = int(d.replace("done_", ""))
        db = load_data()
        pending = [t for t in db.get("tasks", []) if not t.get("done")]
        if idx < len(pending):
            title = pending[idx]["title"]
            for t in db["tasks"]:
                if t["title"] == title and not t.get("done"):
                    t["done"] = True
                    break
            save_data(db)
            await q.edit_message_text(f"🎉 Done: *{title}*\n\n/start দিয়ে menu দেখো", parse_mode="Markdown")

    elif d == "menu_finance":
        await q.edit_message_text(
            "💰 *Finance*\n\n`/income 500 | Client payment`\n`/expense 20 | Canva`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Summary", callback_data="finance_summary")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ]), parse_mode="Markdown")

    elif d == "finance_summary":
        db = load_data()
        m = datetime.now().strftime("%Y-%m")
        inc = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
        exp = sum(e["amount"] for e in db["expenses"] if e["date"].startswith(m))
        bar, prog = get_bar(inc)
        await q.edit_message_text(
            f"💰 *এই মাসের Summary*\n\n🟢 Income: ${inc:.2f}\n🔴 Expense: ${exp:.2f}\n"
            f"💵 Net: ${inc-exp:.2f}\n\n🎯 `{bar}` {prog:.1f}%\nআরো ${max(MONTHLY_GOAL-inc,0):.2f} দরকার",
            reply_markup=back("menu_finance"), parse_mode="Markdown")

    elif d == "menu_goal":
        db = load_data()
        m = datetime.now().strftime("%Y-%m")
        inc = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
        bar, prog = get_bar(inc)
        remaining = max(MONTHLY_GOAL - inc, 0)
        today = datetime.now()
        last_day = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        days_left = max(last_day - today.day, 1)
        daily = remaining / days_left
        mot = "🎉 Goal পূরণ!" if prog >= 100 else "💪 Almost!" if prog >= 75 else "🔥 Focus করো!" if prog >= 50 else "⚡ Outreach বাড়াও!"
        await q.edit_message_text(
            f"🎯 *$5,000 Goal*\n\n`{bar}` {prog:.1f}%\n\n✅ ${inc:.2f}\n📉 Remaining: ${remaining:.2f}\n"
            f"📅 {days_left} days left\n💡 Daily: ${daily:.2f}\n\n{mot}",
            reply_markup=back("back_main"), parse_mode="Markdown")

    elif d == "menu_content":
        await q.edit_message_text(
            "✍️ *AI Content*\n\n`/post topic`\n`/email purpose`\n`/proposal service`\n`/caption topic`",
            reply_markup=back("back_main"), parse_mode="Markdown")

    elif d == "menu_reminders":
        await q.edit_message_text(
            "⏰ *Reminders*\n\n`/remind 30 Call client`\n`/remind 60 Send invoice`",
            reply_markup=back("back_main"), parse_mode="Markdown")

async def add_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/addclient নাম | active | notes`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    name = parts[0].strip()
    status = parts[1].strip() if len(parts) > 1 else "new"
    notes = parts[2].strip() if len(parts) > 2 else ""
    db = load_data()
    db["clients"][name] = {"status": status, "notes": notes, "added": datetime.now().strftime("%Y-%m-%d"), "followup": []}
    save_data(db)
    await update.message.reply_text(f"✅ *{name}* যোগ হয়েছে!", parse_mode="Markdown")

async def followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/followup নাম | message`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    name = parts[0].strip()
    msg = parts[1].strip() if len(parts) > 1 else "Follow up"
    db = load_data()
    if name in db["clients"]:
        db["clients"][name].setdefault("followup", []).append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "note": msg})
        save_data(db)
        await update.message.reply_text(f"📞 *{name}* follow-up log হয়েছে!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ '{name}' নেই।", parse_mode="Markdown")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/addtask কাজ | high`", parse_mode="Markdown")
        return
    parts = " ".join(context.args).split("|")
    title = parts[0].strip()
    priority = parts[1].strip().lower() if len(parts) > 1 else "medium"
    db = load_data()
    db["tasks"].append({"title": title, "priority": priority, "done": False, "created": datetime.now().strftime("%Y-%m-%d %H:%M")})
    save_data(db)
    e = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
    await update.message.reply_text(f"{e} Task যোগ: *{title}*", parse_mode="Markdown")

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/income 500 | Client`", parse_mode="Markdown")
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
        bar, prog = get_bar(monthly)
        await update.message.reply_text(
            f"💰 Income: *${amount:.2f}* ({source})\n\n🎯 `{bar}` {prog:.1f}%\n${monthly:.2f} / $5,000",
            parse_mode="Markdown")
    except Exception:
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
    except Exception:
        await update.message.reply_text("❌ Amount ঠিকমতো দাও।", parse_mode="Markdown")

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_data()
    m = datetime.now().strftime("%Y-%m")
    inc = sum(i["amount"] for i in db["income"] if i["date"].startswith(m))
    pending = len([t for t in db.get("tasks", []) if not t.get("done")])
    active = len([c for c, info in db.get("clients", {}).items() if info.get("status") == "active"])
    bar, prog = get_bar(inc)
    remaining = max(MONTHLY_GOAL - inc, 0)
    today = datetime.now()
    last_day = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
    days_left = max(last_day - today.day, 1)
    await update.message.reply_text(
        f"📊 *Summary — {today.strftime('%d %b %Y')}*\n\n💰 ${inc:.2f}\n`{bar}` {prog:.1f}%\n\n"
        f"✅ Tasks: {pending}\n👥 Clients: {active}\n💡 Daily needed: ${remaining/days_left:.2f}\n\n/start",
        parse_mode="Markdown")

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE, ctype: str):
    if not context.args:
        await update.message.reply_text(f"Topic দাও! `/{ctype} topic`", parse_mode="Markdown")
        return
    topic = " ".join(context.args)
    msg = await update.message.reply_text("✍️ লিখছি...")
    prompts = {
        "post": f"Write an engaging LinkedIn/Facebook post about: {topic}. Add emojis, CTA. Max 300 words.",
        "email": f"Write a professional client email for: {topic}. Include subject line.",
        "proposal": f"Write a service proposal for AI automation agency about: {topic}.",
        "caption": f"Write 3 social media captions for: {topic}. Add hashtags."
    }
    result = ask_ai(prompts.get(ctype, f"Write about: {topic}"))
    if len(result) > 4000: result = result[:3900] + "..."
    await msg.edit_text(f"✍️ *Generated:*\n\n{result}", parse_mode="Markdown")

async def cmd_post(u, c): await generate(u, c, "post")
async def cmd_email(u, c): await generate(u, c, "email")
async def cmd_proposal(u, c): await generate(u, c, "proposal")
async def cmd_caption(u, c): await generate(u, c, "caption")

async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏰ `/remind 30 Call client` — 30 মিনিট পরে remind করবো", parse_mode="Markdown")

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🤔 ভাবছি...")
    result = ask_ai(update.message.text)
    if len(result) > 4000: result = result[:3900] + "..."
    await msg.edit_text(result)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("addclient", add_client))
    app.add_handler(CommandHandler("followup", followup))
    app.add_handler(CommandHandler("addtask", add_task))
    app.add_handler(CommandHandler("income", add_income))
    app.add_handler(CommandHandler("expense", add_expense))
    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(CommandHandler("post", cmd_post))
    app.add_handler(CommandHandler("email", cmd_email))
    app.add_handler(CommandHandler("proposal", cmd_proposal))
    app.add_handler(CommandHandler("caption", cmd_caption))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
    print("🤖 Chitti চালু!")
    app.run_polling()

if __name__ == "__main__":
    main()
