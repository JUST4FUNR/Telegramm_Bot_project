from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
from datetime import datetime, timedelta
from collections import defaultdict

user_messages = defaultdict(list)
MAX_MESSAGES = 10

# API ключ для OpenWeather
API_KEY = "f61ce797754d3967fb38bacd64bf83c6"
URL = "https://api.openweathermap.org/data/2.5/forecast"
CACHE_DURATION = timedelta(minutes=10)


POPULAR_CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Челябинск", "Самара", "Уфа", "Ростов-на-Дону",
    "Ялта", "Сочи"
]

# Кэш и состояния
weather_cache = {}
user_city = {}
WEATHER_IMAGES = {
    "Clear": "https://www.m24.ru/b/d/nBkSUhL2hFEknsu3Lr6BvMKnxdDs95C-yyqYy7jLs2KQeXqLBmmcmzZh59JUtRPBsdaJqSfJd54qEr7t1mNwKSGK7WY=VEpoZSlBk5ojAabi3vJVxw.jpg",      # Солнце
    "Clouds": "https://riabir.ru/wp-content/uploads/2023/07/tuchi.jpeg",     # Облака
    "Rain": "https://avatars.mds.yandex.net/get-weather/5278294/DWNyVKlUTwNPwverWaOc/orig",       # Дождь
    "Drizzle": "https://ybis.ru/wp-content/uploads/2023/09/dozhd-53.webp",    # Мелкий дождь
    "Thunderstorm": "https://issa.pnzreg.ru/upload/iblock/652/q119yw2vpk3rdmvvfrtqldb4nicbx6d4.jpg", # Гроза
    "Snow": "https://i.pinimg.com/736x/9b/aa/6e/9baa6ececfb22598fbabef8b872a99a1.jpg",          # Снег
    "Mist": "https://ulpravda.ru/pictures/news/big/77848_big.jpg",       # Туман
    "Fog": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Nebel_in_der_Region_Rh%C3%B6n_01386.jpg/1200px-Nebel_in_der_Region_Rh%C3%B6n_01386.jpg",           # Туман
    "Haze": "https://ulpravda.ru/pictures/news/big/77848_big.jpg",       # Дымка
    "Smoke": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Nebel_in_der_Region_Rh%C3%B6n_01386.jpg/1200px-Nebel_in_der_Region_Rh%C3%B6n_01386.jpg",      # Дым
    "Dust": "https://asiaplustj.info/sites/default/files/articles/289608/%D0%BF%D0%BE%D0%B3%D0%BE%D0%B4%D0%B0.jpg",       # Пыль
}


async def send_weather(update, context, user_id: int, city: str, period: str):
    now = datetime.utcnow()

    cache_key = city.lower()
    if cache_key not in weather_cache or (now - weather_cache[cache_key]["timestamp"]) > CACHE_DURATION:
        try:
            params = {
                "q": city,
                "appid": API_KEY,
                "units": "metric",
                "lang": "ru"
            }
            response = requests.get(URL, params=params)
            response.raise_for_status()
            data = response.json()
            weather_cache[cache_key] = {"timestamp": now, "data": data}
        except Exception:
            sent = await context.bot.send_message(chat_id=user_id, text="⚠️ Ошибка при получении прогноза.")
            await track_message(sent, user_id, context)
            return
    else:
        data = weather_cache[cache_key]["data"]

    target_time = now
    if period == "3h":
        target_time += timedelta(hours=3)
    elif period == "today":
        target_time = now.replace(hour=15, minute=0)
    elif period == "tomorrow":
        target_time = (now + timedelta(days=1)).replace(hour=12, minute=0)

    forecast = min(
        data["list"],
        key=lambda x: abs(datetime.strptime(x["dt_txt"], "%Y-%m-%d %H:%M:%S") - target_time)
    )

    dt = forecast["dt_txt"]
    temp = forecast["main"]["temp"]
    description = forecast["weather"][0]["description"]
    wind = forecast["wind"]["speed"]
    condition = forecast["weather"][0]["main"]  # Тип погоды

    image_url = WEATHER_IMAGES.get(condition, "https://images.unsplash.com/photo-1502082553048-f009c37129b9")

    caption = (
        f"📍 {city}\n🕒 {dt}\n"
        f"🌡 Температура: {temp:.1f}°C\n"
        f"🌤 {description.capitalize()}\n"
        f"💨 Ветер: {wind} м/с"
    )

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Посмотреть погоду снова", callback_data="repeat")]
    ])
    sent = await context.bot.send_photo(chat_id=user_id, photo=image_url, caption=caption, reply_markup=reply_markup)
    await track_message(sent, user_id, context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_city[user_id] = "Москва"
    await show_main_menu(update, context, user_id)


async def show_main_menu(update, context, user_id: int):
    keyboard = [
        [
            InlineKeyboardButton("Сейчас", callback_data="now"),
            InlineKeyboardButton("Через 3 часа", callback_data="3h"),
        ],
        [
            InlineKeyboardButton("Сегодня", callback_data="today"),
            InlineKeyboardButton("Завтра", callback_data="tomorrow"),
        ],
        [InlineKeyboardButton("📍 Сменить город", callback_data="change_city")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    sent = await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"Здравствуйте! Этот бот подскажет погоду в выбранном городе.\n\n"
            f"📌 Текущий город: {user_city[user_id]}\n"
            f"Выберите интересующий временной промежуток:"
        ),
        reply_markup=reply_markup,
    )
    await track_message(sent, user_id, context)


async def show_city_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(city, callback_data=f"set_city:{city}")]
        for city in POPULAR_CITIES
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text="Выберите город для прогноза:",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data.startswith("set_city:"):
        city = query.data.split(":", 1)[1]
        user_city[user_id] = city
        await query.edit_message_text(f"✅ Город установлен: {city}")
        await show_main_menu(update, context, user_id)

    elif query.data == "change_city":
        await show_city_selection(update, context)

    elif query.data in ("now", "3h", "today", "tomorrow"):
        city = user_city.get(user_id, "Москва")
        await query.delete_message()
        await send_weather(update, context, user_id, city, query.data)

    elif query.data == "repeat":
        await query.answer()
        await show_main_menu(update, context, user_id)


async def track_message(message, user_id, context):
    user_messages[user_id].append(message.message_id)

    if len(user_messages[user_id]) > MAX_MESSAGES:
        to_delete = user_messages[user_id][:-MAX_MESSAGES]
        user_messages[user_id] = user_messages[user_id][-MAX_MESSAGES:]

        for msg_id in to_delete:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except:
                pass

# Запуск бота


def main():
    application = Application.builder().token("7572314461:AAHJSVn05ijPaqNgwb3h7cl9MD7vGVgd3E8").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
