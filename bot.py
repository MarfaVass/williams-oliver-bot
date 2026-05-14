import requests
from bs4 import BeautifulSoup
import re
from flask import Flask, request
import json
import logging

# Включим логирование
logging.basicConfig(level=logging.INFO)

TOKEN = "8481936845:AAGU1B8OzyPlbHTkNXObieihSkacTsfjAqs"
app = Flask(__name__)

SECTIONS = {
    'Ножи и разделочные доски': 'nozi-i-razdelocnye-doski-13182/',
    'Бытовая техника': 'bytovaa-tehnika-13190/',
    'Посуда для приготовления и выпечки': 'posuda-dla-prigotovlenia-i-vypecki-13112/',
}


def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки: {e}")


def parse_section(section_url):
    """Парсинг раздела с отладкой"""
    full_url = f"https://williams-oliver.ru/catalog/{section_url}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    logging.info(f"Начинаю парсинг: {full_url}")

    try:
        response = requests.get(full_url, headers=headers, timeout=30)
        logging.info(f"Статус ответа: {response.status_code}")
        response.encoding = 'utf-8'

        if response.status_code != 200:
            logging.error(f"Плохой статус: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1')
        section_name = title.text.strip() if title else "Раздел"
        logging.info(f"Раздел: {section_name}")

        cards = soup.find_all('a', class_='products-list-item')
        logging.info(f"Найдено карточек: {len(cards)}")

        if not cards:
            return None

        products = []
        product_ids = set()

        for card in cards:
            href = card.get('href', '')
            match = re.search(r'(\d{11})', href)
            if not match or match.group(1) in product_ids:
                continue
            product_ids.add(match.group(1))

            price_elem = card.find('span', class_='products-list-item__price')
            price = 0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_digits = re.sub(r'\D', '', price_text)
                if price_digits:
                    price = float(price_digits)

            is_online = False
            badge = card.find('div', class_='products-list-item__marker-box')
            if badge and 'Только онлайн' in badge.text:
                is_online = True

            if price > 0:
                products.append({'price': price, 'online': is_online})

        logging.info(f"Собрано товаров с ценами: {len(products)}")

        if not products:
            return None

        total = len(products)
        online_count = sum(1 for p in products if p['online'])
        prices = [p['price'] for p in products]

        return {
            'name': section_name,
            'total': total,
            'online': online_count,
            'avg_price': sum(prices) / len(prices),
            'min_price': min(prices),
            'max_price': max(prices)
        }
    except Exception as e:
        logging.error(f"Ошибка парсинга: {e}")
        return None


@app.route('/')
def index():
    return "Бот работает!"


@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return 'ok'

        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        logging.info(f"Получено сообщение: {text}")

        if text == '/start':
            keyboard = {'keyboard': [[s] for s in SECTIONS.keys()], 'resize_keyboard': True}
            send_telegram_message(chat_id, "👋 Выберите раздел каталога:", keyboard)

        elif text in SECTIONS:
            send_telegram_message(chat_id, f"🔍 Анализирую {text}... ⏳")
            stats = parse_section(SECTIONS[text])

            if stats:
                percent = (stats['online'] / stats['total']) * 100
                result = f"*{stats['name']}*\n\n"
                result += f"📦 *Статистика:*\n"
                result += f"• Всего товаров: {stats['total']}\n"
                result += f"• Товаров онлайн: {stats['online']}\n"
                result += f"• Доля онлайн: {percent:.1f}%\n\n"
                result += f"💰 *Цены:*\n"
                result += f"• Средняя цена: {int(stats['avg_price']):,} ₽\n".replace(',', ' ')
                result += f"• Мин. цена: {int(stats['min_price']):,} ₽\n".replace(',', ' ')
                result += f"• Макс. цена: {int(stats['max_price']):,} ₽".replace(',', ' ')
                send_telegram_message(chat_id, result)
            else:
                send_telegram_message(chat_id,
                                      "❌ Не удалось получить данные.\n\nСайт may be недоступен из PythonAnywhere.")

        return 'ok'
    except Exception as e:
        logging.error(f"Ошибка webhook: {e}")
        return 'error'


if __name__ == '__main__':
    app.run()