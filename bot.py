import os
import logging
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "243466293"))
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

VIDEO1_ID = os.environ.get("VIDEO1_ID", "")
VIDEO2_ID = os.environ.get("VIDEO2_ID", "")
VIDEO3_ID = os.environ.get("VIDEO3_ID", "")

INSTAGRAM_URL = "https://www.instagram.com/mikhaildenisov_ap"

ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Ты — продающий ассистент Михаила Денисова, эксперта по международному бизнесу и Google Grants.

Твоя задача — провести потенциального клиента от интереса к записи на личную консультацию с Михаилом.

О продукте:
Михаил помогает предпринимателям выходить на международные рынки и получать бесплатный трафик от Google через программу Google Ad Grants — $10,000 в месяц ($120,000 в год) на рекламу.

Три пакета:

Пакет 1 — "Старт" — 250,000 руб
Стратегический разбор бизнеса + план выхода на международный рынок + обучение как самостоятельно получить Google Grant.
Для тех кто хочет разобраться и сделать своими руками.

Пакет 2 — "НКО под ключ" — 1,000,000 руб
Всё из Старта + мы сами открываем НКО, создаём сайт, проходим верификацию Google, получаем грант.
Клиент получает готовую НКО с $10k/мес трафика без погружения в детали.

Пакет 3 — "Бизнес под ключ" — 3,000,000 руб
Полная инфраструктура: коммерческая компания + счета + бухгалтерия + одна или несколько НКО.
1 НКО = $120k трафика в год. Хочешь $360k — делаем три НКО.
Заходишь в готовую систему и зарабатываешь.

Логика диалога:
1. Начни с вопроса о бизнесе клиента — что есть сейчас, чего хочет достичь
2. Выясни: есть ли продукт/бизнес, какой рынок интересует, есть ли бюджет
3. Предложи подходящий пакет с объяснением почему именно он — покажи математику окупаемости
4. Работай с возражениями уверенно, с цифрами
5. Когда клиент готов — попроси его имя и ник в Telegram для передачи Михаилу

Важно: когда клиент назвал своё имя И ник в Telegram — в самом начале своего ответа добавь скрытую метку (она не отображается клиенту):
LEAD_READY:[имя]|[ник]

Например: LEAD_READY:Александр|@alex_business

После метки — напиши клиенту что Михаил свяжется с ним в течение 24 часов.

Стиль: деловой, живой, без официоза. Не давить — держать инициативу. Максимум 3-4 предложения за раз. Только русский язык."""

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
    "Теперь самое важное — понять, какой формат подходит именно тебе.\n\n"
    "Мой ассистент задаст тебе несколько вопросов и подберёт оптимальное решение. "
    "Это займёт 3-5 минут — и после этого ты будешь знать конкретный следующий шаг.\n\n"
    "Напиши что-нибудь чтобы начать 👇"
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
        context.user_data["ai_active"] = True
        context.user_data["messages"] = []
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO3)


async def ai_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("ai_active"):
        return

    user = update.effective_user
    user_text = update.message.text

    messages = context.user_data.get("messages", [])
    messages.append({"role": "user", "content": user_text})

    # Ограничение — не больше 30 сообщений в диалоге
    if len(messages) > 30:
        await update.message.reply_text(
            "Спасибо за диалог! Михаил свяжется с тобой лично для продолжения разговора."
        )
        context.user_data["ai_active"] = False
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    response = ai_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=messages
    )

    ai_text = response.content[0].text
    messages.append({"role": "assistant", "content": ai_text})
    context.user_data["messages"] = messages

    # Проверяем метку передачи лида
    if ai_text.startswith("LEAD_READY:"):
        lines = ai_text.split("\n", 1)
        lead_line = lines[0].replace("LEAD_READY:", "").strip()
        reply_text = lines[1].strip() if len(lines) > 1 else "Михаил свяжется с тобой в течение 24 часов!"

        parts = lead_line.split("|")
        lead_name = parts[0].strip() if len(parts) > 0 else "—"
        lead_nick = parts[1].strip() if len(parts) > 1 else "—"

        # Формируем историю диалога для Михаила
        history = ""
        for msg in messages[:-1]:
            role = "Клиент" if msg["role"] == "user" else "Агент"
            history += f"{role}: {msg['content']}\n\n"

        notification = (
            f"🔥 Горячий лид!\n\n"
            f"Имя: {lead_name}\n"
            f"Telegram: {lead_nick}\n"
            f"Telegram ID: {user.id} (@{user.username or 'без username'})\n\n"
            f"📋 История диалога:\n\n{history}"
        )

        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=notification[:4000])
        await update.message.reply_text(reply_text)
        context.user_data["ai_active"] = False
    else:
        await update.message.reply_text(ai_text)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_agent))
    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
