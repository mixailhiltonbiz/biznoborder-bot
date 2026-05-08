import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "243466293"))

# Вставь file_id видео после первой загрузки через @BizNoBorder_Bot
VIDEO1_ID = os.environ.get("VIDEO1_ID", "")
VIDEO2_ID = os.environ.get("VIDEO2_ID", "")
VIDEO3_ID = os.environ.get("VIDEO3_ID", "")

INSTAGRAM_URL = "https://www.instagram.com/mikhaildenisov_ap"

WELCOME_TEXT = (
    "Привет! 👋\n\n"
    "Меня зовут Михаил Денисов — я помогаю предпринимателям выходить на "
    "международные рынки и получать доход в валюте.\n\n"
    "Я подготовил для тебя серию из 3 коротких видео. В них — конкретная система: "
    "как легально получать $10,000 в месяц бесплатного трафика от Google "
    "и зарабатывать в долларах из любой точки мира.\n\n"
    "Первое видео уже здесь 👇"
)

TEXT_AFTER_VIDEO1 = (
    "Если ты узнал себя в этом видео — значит, следующее тебе точно нужно.\n\n"
    "Во втором видео я расскажу конкретный инструмент: как работает система "
    "с Google Grants, почему это легально, и почему 140,000 компаний по всему "
    "миру уже этим пользуются — а большинство в России даже не слышали об этом.\n\n"
    f"И да — пока смотришь, подпишись на мой Instagram, там выкладываю кейсы "
    f"и инсайты в живом режиме 👇\n{INSTAGRAM_URL}\n\n"
    "Видео №2 ниже 👇"
)

TEXT_AFTER_VIDEO2 = (
    "$10,000 в месяц трафика — это не теория. Это система, которую мы уже выстроили и запустили.\n\n"
    "В третьем видео я покажу три конкретных формата работы с нами. "
    "От самостоятельного старта с нашей стратегией — до бизнеса под ключ "
    "с компанией, счетами и трафиком от Google уже в первый месяц.\n\n"
    "Последнее видео — самое важное 👇"
)

TEXT_AFTER_VIDEO3 = (
    "Если после этих трёх видео у тебя появился вопрос «а как это работает "
    "именно для меня?» — это правильный вопрос.\n\n"
    "Запишись на бесплатную консультацию. Разберём твою ситуацию и подберём "
    "формат работы который даст результат быстрее всего.\n\n"
    "Напиши прямо здесь:\n"
    "— Как тебя зовут\n"
    "— Ник в Telegram для связи\n"
    "— Пару слов о своём бизнесе или идее\n\n"
    "Свяжемся в течение 24 часов 👇"
)


async def send_video_or_placeholder(chat_id, video_id, label, context, reply_markup=None):
    if video_id:
        await context.bot.send_video(
            chat_id=chat_id,
            video=video_id,
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"[{label} — скоро будет здесь]",
            reply_markup=reply_markup
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton("Смотрел, хочу дальше ▶️", callback_data="after_video1")]]
    await update.message.reply_text(WELCOME_TEXT)
    await send_video_or_placeholder(
        update.effective_chat.id, VIDEO1_ID, "Видео 1", context,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "after_video1":
        keyboard = [[InlineKeyboardButton("Хочу узнать как работать с вами ▶️", callback_data="after_video2")]]
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO1, disable_web_page_preview=True)
        await send_video_or_placeholder(
            chat_id, VIDEO2_ID, "Видео 2", context,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "after_video2":
        keyboard = [[InlineKeyboardButton("Записаться на консультацию ✅", callback_data="after_video3")]]
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO2)
        await send_video_or_placeholder(
            chat_id, VIDEO3_ID, "Видео 3", context,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "after_video3":
        context.user_data["collecting_lead"] = True
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO3)


async def collect_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("collecting_lead"):
        return

    user = update.effective_user
    username = f"@{user.username}" if user.username else "без username"

    notification = (
        f"🔔 Новая заявка на консультацию!\n\n"
        f"От: {user.full_name} ({username})\n"
        f"Telegram ID: {user.id}\n\n"
        f"Сообщение:\n{update.message.text}"
    )

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=notification)
    context.user_data["collecting_lead"] = False

    await update.message.reply_text(
        "Отлично! Заявка принята ✅\n\n"
        "Мы свяжемся с тобой в течение 24 часов. До скорой встречи!"
    )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_lead))
    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
