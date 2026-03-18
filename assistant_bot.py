import os
import json
import asyncio
import datetime
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from groq import Groq

# ── CONFIG ────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = "8645726843:AAGSOjDxh9EhAIlun8B2FilSwVrutP2Gt8k"
GROQ_API_KEY   = "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"

# ── GROQ SETUP ───────────────────────────────────────────────────────────
groq_client = Groq(api_key=GROQ_API_KEY)


# ── DATABASE SETUP ────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("assistant.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task TEXT,
            due_date TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            company TEXT,
            role TEXT,
            status TEXT DEFAULT 'Applied',
            applied_date TEXT,
            notes TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            message TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# ── MAIN MENU KEYBOARD ────────────────────────────────────────────────────
def main_menu():
    keyboard = [
        [KeyboardButton("💬 Chat with AI"), KeyboardButton("💻 Code Help")],
        [KeyboardButton("✅ My Tasks"),     KeyboardButton("➕ Add Task")],
        [KeyboardButton("💼 Job Tracker"),  KeyboardButton("➕ Add Job")],
        [KeyboardButton("📊 My Stats"),     KeyboardButton("🔥 Motivate Me")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ── SYSTEM PROMPT ────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are Divahar's personal AI assistant. 
You know that Divahar is a Software Developer from Chennai/Bengaluru, India.
He is a B.Tech IT graduate working on Java, Spring Boot, React.js, Node.js, MySQL, MongoDB.
He is currently building an HRMS project and looking for Software Developer jobs.

Be friendly, casual, supportive like a best friend.
Use simple English. Occasionally use "bro" naturally.
For code questions: give clean working code with explanation.
For job advice: give practical tips for Indian IT job market.
Keep responses concise but helpful.
"""

# ── ASK GROQ ─────────────────────────────────────────────────────────────
async def ask_gemini(user_id: int, user_message: str) -> str:
    try:
        # Get last 5 messages for context
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("""
            SELECT role, message FROM chat_history
            WHERE user_id = ? ORDER BY id DESC LIMIT 10
        """, (user_id,))
        history = c.fetchall()[::-1]
        conn.close()

        # Build messages for Groq
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for role, msg in history:
            groq_role = "user" if role == "user" else "assistant"
            messages.append({"role": groq_role, "content": msg})
        messages.append({"role": "user", "content": user_message})

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1024,
            temperature=0.7
        )
        reply = response.choices[0].message.content.strip()

        # Save to history
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        now = datetime.datetime.now().isoformat()
        c.execute("INSERT INTO chat_history (user_id, role, message, timestamp) VALUES (?,?,?,?)",
                  (user_id, "user", user_message, now))
        c.execute("INSERT INTO chat_history (user_id, role, message, timestamp) VALUES (?,?,?,?)",
                  (user_id, "assistant", reply, now))
        conn.commit()
        conn.close()

        return reply

    except Exception as e:
        return f"❌ AI error: {str(e)}"

# ══════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Hey {name} bro! 👋 I'm your Personal Assistant!\n\n"
        f"I can help you with:\n"
        f"💬 Chat & General Q&A\n"
        f"💻 Code Help (Java, React, Python...)\n"
        f"✅ Daily Task Reminders\n"
        f"💼 Job Application Tracker\n"
        f"🔥 Motivation & Advice\n\n"
        f"Use the menu below to get started! 🚀",
        reply_markup=main_menu()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Commands:*\n\n"
        "/start — Start the bot\n"
        "/tasks — View all tasks\n"
        "/addtask — Add a new task\n"
        "/jobs — View job tracker\n"
        "/addjob — Add a job application\n"
        "/stats — Your progress stats\n"
        "/clear — Clear chat history\n"
        "/motivate — Get motivation\n\n"
        "Or just *type anything* to chat with AI! 💬",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# ── TASKS ─────────────────────────────────────────────────────────────────
async def view_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("assistant.db")
    c = conn.cursor()
    c.execute("SELECT id, task, due_date, done FROM tasks WHERE user_id=? ORDER BY done, id", (user_id,))
    tasks = c.fetchall()
    conn.close()

    if not tasks:
        await update.message.reply_text(
            "📭 No tasks yet bro!\nClick *➕ Add Task* to add one!",
            parse_mode="Markdown", reply_markup=main_menu()
        )
        return

    text = "📋 *Your Tasks:*\n\n"
    for tid, task, due, done in tasks:
        status = "✅" if done else "⏳"
        due_str = f" | 📅 {due}" if due else ""
        text += f"{status} `[{tid}]` {task}{due_str}\n"

    text += "\n💡 To complete: /done_1 (replace 1 with task ID)\nTo delete: /del_1"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def add_task_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for"] = "task"
    await update.message.reply_text(
        "✅ *Add New Task*\n\nType your task bro!\n"
        "Format: `Task name | DD-MM-YYYY` (date optional)\n\n"
        "Example: `Study Spring Boot | 20-03-2026`",
        parse_mode="Markdown"
    )

async def complete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(update.message.text.split("_")[1])
        user_id = update.effective_user.id
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("UPDATE tasks SET done=1 WHERE id=? AND user_id=?", (task_id, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Task {task_id} marked as done! Great work bro! 🔥", reply_markup=main_menu())
    except:
        await update.message.reply_text("⚠️ Invalid command!", reply_markup=main_menu())

async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(update.message.text.split("_")[1])
        user_id = update.effective_user.id
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🗑️ Task {task_id} deleted!", reply_markup=main_menu())
    except:
        await update.message.reply_text("⚠️ Invalid command!", reply_markup=main_menu())

# ── JOB TRACKER ───────────────────────────────────────────────────────────
async def view_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("assistant.db")
    c = conn.cursor()
    c.execute("SELECT company, role, status, applied_date, notes FROM jobs WHERE user_id=? ORDER BY id DESC", (user_id,))
    jobs = c.fetchall()
    conn.close()

    if not jobs:
        await update.message.reply_text(
            "💼 No job applications yet bro!\nClick *➕ Add Job* to track one!",
            parse_mode="Markdown", reply_markup=main_menu()
        )
        return

    status_emoji = {"Applied": "📤", "Interview": "🎯", "Rejected": "❌", "Offered": "🎉", "Accepted": "✅"}
    text = "💼 *Your Job Applications:*\n\n"
    for company, role, status, date, notes in jobs:
        emoji = status_emoji.get(status, "📋")
        text += f"{emoji} *{company}*\n   └ {role} | {status} | {date}\n"
        if notes:
            text += f"   📝 {notes}\n"
        text += "\n"

    # Summary
    conn = sqlite3.connect("assistant.db")
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM jobs WHERE user_id=? GROUP BY status", (user_id,))
    summary = c.fetchall()
    conn.close()
    text += "📊 *Summary:* "
    for s, cnt in summary:
        text += f"{s}: {cnt}  "

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def add_job_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for"] = "job"
    await update.message.reply_text(
        "💼 *Add Job Application*\n\n"
        "Format: `Company | Role | Status`\n\n"
        "Status options: Applied / Interview / Rejected / Offered / Accepted\n\n"
        "Example: `Razorpay | Software Developer | Applied`",
        parse_mode="Markdown"
    )

# ── STATS ─────────────────────────────────────────────────────────────────
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("assistant.db")
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (user_id,))
    total_tasks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM tasks WHERE user_id=? AND done=1", (user_id,))
    done_tasks = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM jobs WHERE user_id=?", (user_id,))
    total_jobs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='Interview'", (user_id,))
    interviews = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM chat_history WHERE user_id=? AND role='user'", (user_id,))
    chats = c.fetchone()[0]
    conn.close()

    pct = int((done_tasks/total_tasks*100)) if total_tasks > 0 else 0
    bar = "█" * (pct//10) + "░" * (10 - pct//10)

    await update.message.reply_text(
        f"📊 *Your Stats, bro!*\n\n"
        f"✅ Tasks: {done_tasks}/{total_tasks} done\n"
        f"Progress: [{bar}] {pct}%\n\n"
        f"💼 Job Applications: {total_jobs}\n"
        f"🎯 Interviews: {interviews}\n\n"
        f"💬 Total AI Chats: {chats}\n\n"
        f"Keep going bro! 💪🔥",
        parse_mode="Markdown", reply_markup=main_menu()
    )

# ── MOTIVATE ──────────────────────────────────────────────────────────────
async def motivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = await ask_gemini(
        update.effective_user.id,
        "Give me a short powerful motivational message for a software developer "
        "who is job hunting and building projects. Make it personal and energetic! Max 5 lines."
    )
    await update.message.reply_text(f"🔥 *Motivation for you bro!*\n\n{reply}", parse_mode="Markdown", reply_markup=main_menu())

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("assistant.db")
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑️ Chat history cleared bro! Fresh start! 🚀", reply_markup=main_menu())

# ── MAIN MESSAGE HANDLER ──────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # ── Menu buttons ──
    if text == "💬 Chat with AI":
        context.user_data["waiting_for"] = "chat"
        await update.message.reply_text("💬 Chat mode ON! Ask me anything bro! 🤖\n\nType your question:", reply_markup=main_menu())
        return
    elif text == "💻 Code Help":
        context.user_data["waiting_for"] = "code"
        await update.message.reply_text("💻 Code mode ON! What language or problem bro?\n\nType your code question:", reply_markup=main_menu())
        return
    elif text == "✅ My Tasks":
        await view_tasks(update, context); return
    elif text == "➕ Add Task":
        await add_task_prompt(update, context); return
    elif text == "💼 Job Tracker":
        await view_jobs(update, context); return
    elif text == "➕ Add Job":
        await add_job_prompt(update, context); return
    elif text == "📊 My Stats":
        await stats(update, context); return
    elif text == "🔥 Motivate Me":
        await motivate(update, context); return

    # ── Dynamic commands /done_X /del_X ──
    if text.startswith("/done_"):
        await complete_task(update, context); return
    if text.startswith("/del_"):
        await delete_task(update, context); return

    # ── Waiting for input ──
    waiting = context.user_data.get("waiting_for", "chat")

    if waiting == "task":
        parts = text.split("|")
        task_name = parts[0].strip()
        due_date = parts[1].strip() if len(parts) > 1 else ""
        conn = sqlite3.connect("assistant.db")
        c = conn.cursor()
        c.execute("INSERT INTO tasks (user_id, task, due_date, created_at) VALUES (?,?,?,?)",
                  (user_id, task_name, due_date, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        context.user_data["waiting_for"] = "chat"
        await update.message.reply_text(f"✅ Task added bro!\n📌 *{task_name}*" + (f"\n📅 Due: {due_date}" if due_date else ""), parse_mode="Markdown", reply_markup=main_menu())
        return

    if waiting == "job":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 2:
            company = parts[0]
            role = parts[1]
            status = parts[2] if len(parts) > 2 else "Applied"
            conn = sqlite3.connect("assistant.db")
            c = conn.cursor()
            c.execute("INSERT INTO jobs (user_id, company, role, status, applied_date) VALUES (?,?,?,?,?)",
                      (user_id, company, role, status, datetime.datetime.now().strftime("%d-%m-%Y")))
            conn.commit()
            conn.close()
            context.user_data["waiting_for"] = "chat"
            await update.message.reply_text(
                f"💼 Job added bro!\n\n🏢 *{company}*\n💼 {role}\n📊 Status: {status}",
                parse_mode="Markdown", reply_markup=main_menu()
            )
        else:
            await update.message.reply_text("⚠️ Format: `Company | Role | Status`", parse_mode="Markdown")
        return

    # ── Default: AI Chat ──
    await update.message.reply_chat_action("typing")
    if waiting == "code":
        prompt = f"Code help request: {text}\nGive clean working code with brief explanation."
    else:
        prompt = text

    reply = await ask_gemini(user_id, prompt)
    await update.message.reply_text(reply, reply_markup=main_menu())

# ── VOICE MESSAGE HANDLER ─────────────────────────────────────────────────
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎤 Voice received bro! Voice transcription needs Whisper API.\n"
        "For now, please type your message! 💬",
        reply_markup=main_menu()
    )

# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════
def main():
    init_db()
    print("🤖 Divahar Assistant Bot starting...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("tasks", view_tasks))
    app.add_handler(CommandHandler("addtask", add_task_prompt))
    app.add_handler(CommandHandler("jobs", view_jobs))
    app.add_handler(CommandHandler("addjob", add_job_prompt))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("motivate", motivate))
    app.add_handler(CommandHandler("clear", clear_history))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("✅ Bot is running! Open Telegram → @divahar_assistant_bot")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()