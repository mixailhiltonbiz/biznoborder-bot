import os
import json
import logging
import traceback
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

VIDEO1_URL = "https://youtu.be/M2NyDdw9Phc"
VIDEO2_URL = "https://youtu.be/h8gk30CQNww"
VIDEO3_URL = "https://youtu.be/smPkj7RzjFE"

INSTAGRAM_URL = "https://www.instagram.com/mikhaildenisov_ap"

CALC_USD_RATE = 95
CALC_GRANT_BUDGET_USD = 8650
CALC_GRANT_EFFICIENCY = 0.7
CALC_DEFAULT_CONV_LEAD_SALE = 12
CALC_DEFAULT_MARGIN = 40
CALC_DEFAULT_CPL_B2C = 5000
CALC_DEFAULT_CPL_B2B = 12000
CALC_B2B_TICKET_THRESHOLD = 100000
CALC_PACKAGE_PRICE = 1_000_000

ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def notify_admin_ai_failure(context, user, where, error, user_text=None):
    """Шлёт Михаилу уведомление когда AI-вызов упал."""
    err_str = f"{type(error).__name__}: {error}"[:1000]
    user_text_short = (user_text or "")[:300]
    msg = (
        f"🚨 Сбой бота в {where}\n\n"
        f"User: @{user.username or 'без username'} (id {user.id})\n"
        f"Имя: {user.full_name}\n\n"
        f"Сообщение пользователя:\n{user_text_short}\n\n"
        f"Ошибка:\n{err_str}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg[:4000])
    except Exception:
        logger.exception("Failed to notify admin")


async def error_handler(update, context):
    """Глобальная сетка безопасности — ловит ЛЮБУЮ необработанную ошибку в любом хендлере."""
    logger.exception("Unhandled error", exc_info=context.error)
    tb = "".join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__))
    user_info = "unknown"
    if isinstance(update, Update) and update.effective_user:
        u = update.effective_user
        user_info = f"@{u.username or 'без username'} (id {u.id}, {u.full_name})"
    msg = (
        f"🚨 Необработанная ошибка в боте\n\n"
        f"User: {user_info}\n\n"
        f"Traceback:\n{tb[-2500:]}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg[:4000])
    except Exception:
        logger.exception("Failed to send error notification to admin")

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("▶️ Смотреть видео №1", url=VIDEO1_URL)],
        [InlineKeyboardButton("Смотрел, хочу дальше →", callback_data="after_video1")]
    ]
    await update.message.reply_text(WELCOME_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "after_video1":
        keyboard = [
            [InlineKeyboardButton("▶️ Смотреть видео №2", url=VIDEO2_URL)],
            [InlineKeyboardButton("Хочу узнать как работать с вами →", callback_data="after_video2")]
        ]
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO1,
                                       reply_markup=InlineKeyboardMarkup(keyboard),
                                       disable_web_page_preview=True)

    elif query.data == "after_video2":
        keyboard = [
            [InlineKeyboardButton("▶️ Смотреть видео №3", url=VIDEO3_URL)],
            [InlineKeyboardButton("Записаться на консультацию ✅", callback_data="after_video3")]
        ]
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO2,
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "after_video3":
        context.user_data["ai_active"] = True
        context.user_data["messages"] = []
        await context.bot.send_message(chat_id=chat_id, text=TEXT_AFTER_VIDEO3)

    elif query.data == "calc_to_ai":
        context.user_data["calc_step"] = None
        context.user_data["ai_active"] = True
        context.user_data["messages"] = []
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "Окей, разберём твою ситуацию.\n"
                "Расскажи в двух словах: какой у тебя бизнес и что ты сейчас "
                "хочешь — больше лидов, выход в валюту, что-то ещё?"
            )
        )

    elif query.data == "calc_to_videos":
        context.user_data["calc_step"] = None
        keyboard = [
            [InlineKeyboardButton("▶️ Смотреть видео №1", url=VIDEO1_URL)],
            [InlineKeyboardButton("Смотрел, хочу дальше →", callback_data="after_video1")]
        ]
        await context.bot.send_message(
            chat_id=chat_id,
            text="3 коротких видео — как это устроено изнутри. Начнём с первого 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "calc_share":
        share_text = (
            "Поделись калькулятором — кому-то из знакомых это сэкономит миллионы:\n\n"
            "Калькулятор упущенной прибыли от Google Grants\n"
            "Введи 5 цифр — увидишь сколько ты теряешь каждый месяц без НКО.\n"
            "👉 @BizNoBorder_Bot — команда /calc"
        )
        await context.bot.send_message(chat_id=chat_id, text=share_text)


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

    try:
        response = ai_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        ai_text = response.content[0].text
    except Exception as e:
        logger.exception("AI agent (ai_agent) failed")
        await notify_admin_ai_failure(context, user, "ai_agent", e, user_text)
        await update.message.reply_text(
            "Извини, технический сбой. Михаил уже получил уведомление — "
            "напиши /start через минуту, либо напрямую @MikhailDe."
        )
        return
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


CALC_SKIP_WORDS = {"пропустить", "skip", "—", "-", "не знаю", "хз"}


def parse_number(text: str):
    """Возвращает int или None если 'пропустить'. Бросает ValueError при невалидном вводе."""
    t = text.strip().lower().replace(" ", "").replace(" ", "")
    if t in CALC_SKIP_WORDS:
        return None
    multiplier = 1
    if t.endswith(("к", "k", "тыс")):
        multiplier = 1000
        t = t.rstrip("ктыс").rstrip("k")
    elif t.endswith(("м", "m", "млн")):
        multiplier = 1_000_000
        t = t.rstrip("ммлн").rstrip("m")
    t = t.rstrip("%₽$руб")
    # Разделители тысяч vs десятичная дробь: '500.000' / '500,000' / '1.500.000' = тысячи,
    # '1.5' / '1,5' = десятичная.
    seps = [c for c in t if c in ".,"]
    if len(seps) > 1:
        t = t.replace(".", "").replace(",", "")
    elif len(seps) == 1:
        idx = max(t.find("."), t.find(","))
        after = t[idx + 1:]
        if len(after) == 3 and after.isdigit():
            t = t.replace(".", "").replace(",", "")
        else:
            t = t.replace(",", ".")
    return int(float(t) * multiplier)


def parse_conv(text: str, leads: int):
    """Конверсия: процент (например '20') или количество продаж (например '8'). None если пропустить."""
    n = parse_number(text)
    if n is None:
        return None
    if n <= 100 and (leads is None or n <= leads or n <= 50):
        return n
    if leads and n > leads:
        return None
    return n


CALC_INTRO = (
    "📊 Калькулятор упущенной прибыли от Google Grants\n\n"
    "5 вопросов, ~2 минуты.\n"
    "Покажу сколько вы недополучаете каждый месяц без НКО.\n\n"
    "Если каких-то цифр не знаете — напишите \"пропустить\", "
    "подставлю отраслевые средние.\n\n"
    "Поехали 👇"
)

CALC_Q1 = (
    "1/5. Сколько вы тратите на платную рекламу в месяц?\n"
    "(Google Ads + Я.Директ + соцсети, всё суммарно, в ₽)\n\n"
    "Пример: 400000 или 400к"
)

CALC_Q2 = "2/5. Какой у вас средний чек одной продажи в ₽?"

CALC_Q3 = (
    "3/5. Сколько заявок (лидов) приходит с этого бюджета в месяц?\n"
    "Не знаете — напишите \"пропустить\"."
)

CALC_Q4 = (
    "4/5. Какая конверсия из заявки в продажу?\n"
    "Введите % (например \"20\") или количество продаж (например \"8\").\n"
    "Не знаете — \"пропустить\"."
)

CALC_Q5 = (
    "5/5. Маржа с одной продажи в %?\n"
    "Маржа = (цена − себестоимость) / цена × 100\n"
    "Не знаете — \"пропустить\" (поставлю 40%)."
)


async def calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["calc_step"] = 1
    context.user_data["calc_data"] = {}
    await update.message.reply_text(CALC_INTRO)
    await update.message.reply_text(CALC_Q1)


async def calc_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data["calc_step"]
    data = context.user_data["calc_data"]
    text = update.message.text

    if step == 1:
        try:
            n = parse_number(text)
            if n is None or n < 0:
                await update.message.reply_text("Нужна цифра. Сколько тратите в ₽? Пример: 400000")
                return
            data["ad_spend"] = n
            if n == 0:
                await update.message.reply_text(
                    "Бюджет 0 — окей. Тогда грант для вас будет основным каналом.\n"
                    "Считаем с нуля 👇"
                )
            else:
                await update.message.reply_text(f"Записал: {n:,} ₽/мес ≈ ${n // CALC_USD_RATE:,}".replace(",", " "))
            context.user_data["calc_step"] = 2
            await update.message.reply_text(CALC_Q2)
        except (ValueError, AttributeError):
            await update.message.reply_text("Не распознал цифру. Попробуй ещё раз. Пример: 400000")
        return

    if step == 2:
        try:
            n = parse_number(text)
            if n is None or n <= 0:
                await update.message.reply_text("Нужен средний чек в ₽. Пример: 50000")
                return
            data["avg_ticket"] = n
            await update.message.reply_text(f"Средний чек: {n:,} ₽".replace(",", " "))
            context.user_data["calc_step"] = 3
            await update.message.reply_text(CALC_Q3)
        except (ValueError, AttributeError):
            await update.message.reply_text("Не распознал. Попробуй ещё раз.")
        return

    if step == 3:
        try:
            n = parse_number(text)
            if n is not None and n < 0:
                await update.message.reply_text("Не понял. Сколько заявок в месяц? Или \"пропустить\".")
                return
            data["leads"] = n
            if n is None:
                default_cpl = (
                    CALC_DEFAULT_CPL_B2B
                    if data["avg_ticket"] >= CALC_B2B_TICKET_THRESHOLD
                    else CALC_DEFAULT_CPL_B2C
                )
                est_leads = data["ad_spend"] // default_cpl if data["ad_spend"] else 0
                await update.message.reply_text(
                    f"Окей, подставлю средние: ~{est_leads} заявок при CPL {default_cpl:,} ₽".replace(",", " ")
                )
                data["cpl"] = default_cpl
                data["leads_estimated"] = True
            else:
                if data["ad_spend"] > 0 and n > 0:
                    cpl = data["ad_spend"] // n
                    data["cpl"] = cpl
                    await update.message.reply_text(f"{n} заявок/мес. Стоимость лида: {cpl:,} ₽".replace(",", " "))
                else:
                    data["cpl"] = (
                        CALC_DEFAULT_CPL_B2B
                        if data["avg_ticket"] >= CALC_B2B_TICKET_THRESHOLD
                        else CALC_DEFAULT_CPL_B2C
                    )
                    await update.message.reply_text(f"Принял: {n} заявок.")
                data["leads_estimated"] = False
            context.user_data["calc_step"] = 4
            await update.message.reply_text(CALC_Q4)
        except (ValueError, AttributeError):
            await update.message.reply_text("Не распознал. Введи число или \"пропустить\".")
        return

    if step == 4:
        try:
            leads = data.get("leads")
            n = parse_conv(text, leads)
            if n is None and text.strip().lower() not in CALC_SKIP_WORDS:
                await update.message.reply_text("Введи % или количество продаж. Или \"пропустить\".")
                return
            if n is None:
                data["conv_lead_sale"] = CALC_DEFAULT_CONV_LEAD_SALE
                await update.message.reply_text(f"Подставлю среднее: {CALC_DEFAULT_CONV_LEAD_SALE}%")
            elif leads and n <= leads and n > 0:
                pct = round(n / leads * 100, 1)
                data["conv_lead_sale"] = pct
                await update.message.reply_text(f"{n} продаж = {pct}% конверсия")
            else:
                data["conv_lead_sale"] = n
                await update.message.reply_text(f"Конверсия: {n}%")
            context.user_data["calc_step"] = 5
            await update.message.reply_text(CALC_Q5)
        except (ValueError, AttributeError):
            await update.message.reply_text("Не распознал. Введи % или количество. Или \"пропустить\".")
        return

    if step == 5:
        try:
            n = parse_number(text)
            if n is None:
                data["margin"] = CALC_DEFAULT_MARGIN
            elif 0 < n <= 100:
                data["margin"] = n
            else:
                await update.message.reply_text("Маржа в % от 1 до 100. Попробуй ещё раз или \"пропустить\".")
                return
            await update.message.reply_text("Считаю... 🧮")
            await send_calc_result(update, context)
            context.user_data["calc_step"] = None
        except (ValueError, AttributeError):
            await update.message.reply_text("Не распознал. Введи % или \"пропустить\".")
        return


def calculate_grant_profit(ad_spend, avg_ticket, leads=None, conv_lead_sale=None, margin=None):
    """Чистая формула расчёта упущенной прибыли. Возвращает dict с числами для презентации."""
    if margin is None:
        margin = CALC_DEFAULT_MARGIN
    if conv_lead_sale is None:
        conv_lead_sale = CALC_DEFAULT_CONV_LEAD_SALE

    default_cpl = (
        CALC_DEFAULT_CPL_B2B if avg_ticket >= CALC_B2B_TICKET_THRESHOLD else CALC_DEFAULT_CPL_B2C
    )
    if leads is not None and ad_spend > 0 and leads > 0:
        cpl = ad_spend / leads
    else:
        cpl = default_cpl
        if leads is None and ad_spend > 0:
            leads = ad_spend / cpl

    leads_now = leads if leads else 0
    sales_now = leads_now * conv_lead_sale / 100
    revenue_now = sales_now * avg_ticket
    profit_now = revenue_now * margin / 100

    grant_rub = CALC_GRANT_BUDGET_USD * CALC_USD_RATE
    eff_grant = grant_rub * CALC_GRANT_EFFICIENCY
    leads_grant = eff_grant / cpl if cpl > 0 else 0
    sales_grant = leads_grant * conv_lead_sale / 100
    revenue_grant = sales_grant * avg_ticket
    profit_grant_month = revenue_grant * margin / 100
    profit_grant_year = profit_grant_month * 12
    payback_months = CALC_PACKAGE_PRICE / profit_grant_month if profit_grant_month > 0 else None

    if profit_grant_month >= 200_000:
        verdict = "очень выгодно — окупаемость меньше полугода"
    elif profit_grant_month >= 80_000:
        verdict = "считается — окупаемость в пределах года"
    else:
        verdict = "на текущем масштабе грант не приоритет, сначала база"

    return {
        "cpl_rub": round(cpl),
        "leads_now": round(leads_now),
        "sales_now": round(sales_now, 1),
        "profit_now_month_rub": round(profit_now),
        "effective_grant_budget_rub": round(eff_grant),
        "leads_grant": round(leads_grant),
        "sales_grant": round(sales_grant, 1),
        "profit_grant_month_rub": round(profit_grant_month),
        "profit_grant_year_rub": round(profit_grant_year),
        "package_price_rub": CALC_PACKAGE_PRICE,
        "payback_months": round(payback_months, 1) if payback_months else None,
        "verdict": verdict,
        "assumptions": {
            "usd_rate": CALC_USD_RATE,
            "grant_efficiency_pct": int(CALC_GRANT_EFFICIENCY * 100),
            "used_default_margin": margin == CALC_DEFAULT_MARGIN,
            "used_default_conv": conv_lead_sale == CALC_DEFAULT_CONV_LEAD_SALE,
        }
    }


async def send_calc_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["calc_data"]

    ad_spend = d["ad_spend"]
    ticket = d["avg_ticket"]
    cpl = d["cpl"]
    conv = d["conv_lead_sale"]
    margin = d["margin"]
    leads_now = d.get("leads") if d.get("leads") is not None else (ad_spend // cpl if ad_spend else 0)

    sales_now = leads_now * conv / 100
    revenue_now = sales_now * ticket
    profit_now = revenue_now * margin / 100

    grant_budget_rub = CALC_GRANT_BUDGET_USD * CALC_USD_RATE
    effective_grant = grant_budget_rub * CALC_GRANT_EFFICIENCY
    leads_grant = effective_grant / cpl
    sales_grant = leads_grant * conv / 100
    revenue_grant = sales_grant * ticket
    profit_grant_month = revenue_grant * margin / 100
    profit_grant_year = profit_grant_month * 12
    payback_months = CALC_PACKAGE_PRICE / profit_grant_month if profit_grant_month > 0 else 999

    def fmt(n):
        return f"{int(round(n)):,}".replace(",", " ")

    if profit_grant_month >= 200_000:
        verdict_emoji = "🔥"
        verdict = "ОЧЕНЬ выгодно. Окупаемость меньше полугода."
    elif profit_grant_month >= 80_000:
        verdict_emoji = "✅"
        verdict = "Считается. Окупаемость в пределах года."
    else:
        verdict_emoji = "⚠️"
        verdict = "На вашем масштабе грант не приоритет. Сначала база."

    result = (
        f"📊 ВАШИ ЦИФРЫ\n\n"
        f"Сейчас:\n"
        f"• Бюджет рекламы: {fmt(ad_spend)} ₽\n"
        f"• Лидов: ~{int(leads_now)}\n"
        f"• Продаж: ~{int(sales_now)}\n"
        f"• Прибыль с рекламы: {fmt(profit_now)} ₽/мес\n\n"
        f"С Google Grant (консервативно):\n"
        f"• Дополнительный бюджет от Google: ~{fmt(effective_grant)} ₽\n"
        f"• Дополнительных лидов: ~{int(leads_grant)}\n"
        f"• Дополнительных продаж: ~{int(sales_grant)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ВЫ НЕДОПОЛУЧАЕТЕ\n"
        f"   {fmt(profit_grant_month)} ₽ каждый месяц\n"
        f"   {fmt(profit_grant_year)} ₽ за год\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Пакет \"НКО под ключ\": {fmt(CALC_PACKAGE_PRICE)} ₽\n"
        f"Окупается за {payback_months:.1f} мес.\n"
        f"Дальше — чистая дополнительная прибыль.\n\n"
        f"{verdict_emoji} {verdict}\n\n"
        f"Расчёт: курс {CALC_USD_RATE} ₽/$, грант используется на "
        f"{int(CALC_GRANT_EFFICIENCY*100)}% от максимума, ваши же конверсии."
    )

    keyboard = [
        [InlineKeyboardButton("Разобрать мою ситуацию с Михаилом", callback_data="calc_to_ai")],
        [InlineKeyboardButton("Посмотреть 3 видео как это работает", callback_data="calc_to_videos")],
        [InlineKeyboardButton("Поделиться калькулятором", callback_data="calc_share")],
    ]
    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(keyboard))

    admin_msg = (
        f"📊 Кто-то прошёл калькулятор\n\n"
        f"User: @{update.effective_user.username or 'нет username'} (id {update.effective_user.id})\n"
        f"Бюджет: {fmt(ad_spend)} ₽ | Чек: {fmt(ticket)} ₽ | "
        f"Лидов: {int(leads_now)} | Конв: {conv}% | Маржа: {margin}%\n"
        f"Прибыль с гранта: {fmt(profit_grant_month)} ₽/мес | Окупаемость: {payback_months:.1f} мес"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg)
    except Exception as e:
        logger.warning(f"Failed to notify admin: {e}")


CALC_AI_SYSTEM_PROMPT = """Ты — финансовый ассистент Михаила Денисова. Твоя единственная задача в этом диалоге — собрать у клиента 5 цифр и посчитать сколько он недополучает прибыли каждый месяц без Google Ad Grant.

Тебе нужны 5 параметров:
1. ad_spend — текущий бюджет на платную рекламу в месяц (Google Ads + Я.Директ + соцсети суммарно), ₽
2. avg_ticket — средний чек одной продажи, ₽
3. leads — заявок (лидов) в месяц с этого бюджета. Если клиент не знает — оставь пустым (формула подставит средние)
4. conv_lead_sale — конверсия из заявки в продажу в %. Если клиент назвал количество продаж — посчитай % сам. Не знает — оставь пустым
5. margin — маржа с продажи в %. Не знает — оставь пустым (формула поставит 40%)

КАК ВЕСТИ ДИАЛОГ:
- Говори живо, не как анкета. Реагируй на то что клиент написал
- Если клиент в одном сообщении назвал несколько цифр — забирай все, не переспрашивай
- Если рассказал про бизнес — задавай вопросы в контексте (онлайн-школа, товарный, B2B услуги, маркетплейс)
- Реагируй на цифры: «10к за лид — много» или «5% конверсия — низковато». Это показывает экспертизу
- НЕ продавай продукт. Твоя задача — посчитать. Продажа уже происходит в результате расчёта
- Если клиент явно сопротивляется или не хочет отвечать — отстань с этой цифрой, иди дальше
- Максимум 1-2 предложения за реплику. Без воды
- Спрашивай не более одной цифры за раз

КАК ПОНЯТЬ ЧТО ДАННЫХ ХВАТАЕТ:
- Тебе обязательно нужны ad_spend и avg_ticket
- Остальное (leads, conv_lead_sale, margin) можно оставить пустым — формула подставит средние
- Как только у тебя есть ad_spend + avg_ticket + хотя бы попытка собрать остальные 3 → вызывай calculate_grant_profit

ПОСЛЕ ВЫЗОВА ИНСТРУМЕНТА:
- Получишь dict с цифрами
- Презентуй РЕЗКО и ПРЯМО, как Михаил:
  • Главное — «вы недополучаете X рублей каждый месяц / Y в год»
  • Окупаемость пакета НКО под ключ (1М ₽)
  • Если payback_months > 12 или verdict про «не приоритет» — будь честным: скажи что на этом масштабе грант не приоритет
  • Если used_default_margin или used_default_conv = true — упомяни что часть цифр подставлены, точность ±20%
- Закончи фразой типа «Хочешь разобрать твою ситуацию глубже? Скажи — переключу на разговор с Михаилом» — но НЕ дави

ГОЛОС МИХАИЛА:
- Короткие удары: «Математика не врёт.» «Это не теория.» «Окей, считаем.»
- Прямой, провокационный, без официоза
- Без слов: синергия, трансформация, инновационный, уникальный, эффективный
- Без эмодзи в начале фраз — только если очень в тему

Стартовая фраза диалога (если клиент только зашёл): спроси коротко про бизнес и бюджет рекламы. Без длинных вступлений.
"""

CALC_TOOL = {
    "name": "calculate_grant_profit",
    "description": (
        "Считает упущенную прибыль клиента от отсутствия Google Ad Grant. "
        "Вызывай когда собрал ad_spend и avg_ticket (это обязательно), "
        "и хотя бы попытался узнать leads / conv_lead_sale / margin. "
        "Параметры которые клиент не знает — не передавай (формула подставит средние)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ad_spend": {
                "type": "number",
                "description": "Текущий бюджет на платную рекламу в месяц, в рублях. Обязательно."
            },
            "avg_ticket": {
                "type": "number",
                "description": "Средний чек одной продажи, в рублях. Обязательно."
            },
            "leads": {
                "type": "number",
                "description": "Заявок (лидов) в месяц. Не передавай если клиент не знает."
            },
            "conv_lead_sale": {
                "type": "number",
                "description": "Конверсия из заявки в продажу, в %. Не передавай если клиент не знает."
            },
            "margin": {
                "type": "number",
                "description": "Маржа с продажи, в %. Не передавай если клиент не знает."
            },
        },
        "required": ["ad_spend", "avg_ticket"]
    }
}


async def calc_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["calc_ai_active"] = True
    context.user_data["calc_ai_messages"] = []
    context.user_data["calc_ai_done"] = False
    await update.message.reply_text(
        "Окей, посчитаем сколько ты теряешь без Google Grant.\n"
        "Расскажи в двух словах — какой у тебя бизнес и сколько примерно "
        "тратишь на рекламу в месяц?"
    )


def _format_calc_result_for_admin(user, calc_input, result):
    def fmt(n):
        return f"{int(round(n)):,}".replace(",", " ")
    return (
        f"📊 Прохождение калькулятора\n\n"
        f"User: @{user.username or 'без username'} (id {user.id})\n"
        f"Бюджет: {fmt(calc_input.get('ad_spend', 0))} ₽ | "
        f"Чек: {fmt(calc_input.get('avg_ticket', 0))} ₽\n"
        f"Лидов: {calc_input.get('leads', '?')} | "
        f"Конв: {calc_input.get('conv_lead_sale', '?')}% | "
        f"Маржа: {calc_input.get('margin', '?')}%\n\n"
        f"Доп. прибыль с гранта: {fmt(result['profit_grant_month_rub'])} ₽/мес "
        f"= {fmt(result['profit_grant_year_rub'])} ₽/год\n"
        f"Окупаемость пакета 1М: {result['payback_months']} мес\n"
        f"Вердикт: {result['verdict']}"
    )


async def calc_ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user = update.effective_user
    messages = context.user_data.get("calc_ai_messages", [])
    messages.append({"role": "user", "content": user_text})

    # Защита от бесконечного диалога
    if len(messages) > 40:
        await update.message.reply_text(
            "Слишком долгий разговор. Если хочешь — напиши Михаилу напрямую, разберём."
        )
        context.user_data["calc_ai_active"] = False
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    calc_result_this_turn = None
    calc_input_this_turn = None

    # Tool use loop — Claude может попросить вызвать инструмент, мы возвращаем результат, он отвечает текстом
    for _ in range(5):  # макс 5 итераций tool use в одном ходе
        try:
            response = ai_client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=800,
                system=[{
                    "type": "text",
                    "text": CALC_AI_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=[CALC_TOOL],
                messages=messages,
            )
        except Exception as e:
            logger.exception("AI agent (calc_ai_handler) failed")
            await notify_admin_ai_failure(context, user, "calc_ai_handler", e, user_text)
            await update.message.reply_text(
                "Извини, технический сбой в калькуляторе. Михаил уже знает — "
                "попробуй через минуту или напиши ему лично @MikhailDe."
            )
            context.user_data["calc_ai_messages"] = messages
            return

        # сохраняем ассистент-блок целиком (текст + tool_use)
        assistant_blocks = [block.model_dump() for block in response.content]
        messages.append({"role": "assistant", "content": assistant_blocks})

        if response.stop_reason == "tool_use":
            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if not tool_use:
                break
            try:
                result = calculate_grant_profit(**tool_use.input)
                calc_result_this_turn = result
                calc_input_this_turn = tool_use.input
                tool_result_content = json.dumps(result, ensure_ascii=False)
                is_error = False
            except Exception as e:
                logger.exception("calc_tool error")
                tool_result_content = f"Ошибка расчёта: {e}"
                is_error = True

            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_result_content,
                    "is_error": is_error,
                }],
            })
            # цикл продолжается — Claude теперь должен ответить текстом
            continue

        # stop_reason == "end_turn" или другое — финальный текст
        text_block = next((b for b in response.content if b.type == "text"), None)
        final_text = text_block.text if text_block else "..."

        # если в этом ходе был сделан расчёт — показываем 3 кнопки и шлём уведомление админу
        if calc_result_this_turn is not None and not context.user_data.get("calc_ai_done"):
            keyboard = [
                [InlineKeyboardButton("Разобрать мою ситуацию с Михаилом", callback_data="calc_to_ai")],
                [InlineKeyboardButton("Посмотреть 3 видео как это работает", callback_data="calc_to_videos")],
                [InlineKeyboardButton("Поделиться калькулятором", callback_data="calc_share")],
            ]
            await update.message.reply_text(final_text, reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["calc_ai_done"] = True
            try:
                admin_msg = _format_calc_result_for_admin(user, calc_input_this_turn, calc_result_this_turn)
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg)
            except Exception as e:
                logger.warning(f"Failed to notify admin: {e}")
        else:
            await update.message.reply_text(final_text)
        break
    else:
        # вышли по лимиту итераций
        await update.message.reply_text("Что-то пошло не так с расчётом. Напиши Михаилу напрямую.")

    context.user_data["calc_ai_messages"] = messages


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("calc_ai_active"):
        await calc_ai_handler(update, context)
        return
    if context.user_data.get("calc_step"):
        await calc_step(update, context)
        return
    if context.user_data.get("ai_active"):
        await ai_agent(update, context)
        return
    # fallback — пользователь пишет в бота без активной сессии
    keyboard = [
        [InlineKeyboardButton("▶️ Смотреть видео №1", url=VIDEO1_URL)],
        [InlineKeyboardButton("Смотрел, хочу дальше →", callback_data="after_video1")],
    ]
    await update.message.reply_text(
        "Привет! Чтобы начать — нажми /start или /calc (калькулятор упущенной прибыли).\n\n"
        "Или сразу первое видео 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("calc", calc_ai_start))
    app.add_handler(CommandHandler("calcform", calc_start))  # fallback: жёсткая форма
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    app.add_error_handler(error_handler)
    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
