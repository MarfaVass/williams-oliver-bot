 import os
import requests
from bs4 import BeautifulSoup
import re
from flask import Flask, request
import json
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен берется из переменной окружения
TOKEN = os.getenv('BOT_TOKEN')

app = Flask(__name__)

# Разделы каталога
SECTIONS = {
    'Ножи и разделочные доски': 'nozi-i-razdelocnye-doski-13182/',
    'Бытовая техника': 'bytovaa-tehnika-13190/',
    'Посуда для приготовления и выпечки': 'posuda-dla-prigotovlenia-i-vypecki-13112/',
    'Подарки': 'podarki-13342/',
    'Сервизы и сервировка стола': 'servizy-i-servirovka-stola-13138/',
    'Бакалея': 'bakalea-13208/',
    'Кухонные принадлежности': 'kuhonnye-prinadleznosti-13123/',
    'Подарки и декор интерьера': 'podarki-i-dekor-inter-era-13291/',
    'Свечи и ароматы для дома': 'sveci-i-aromaty-dla-doma-13288/',
    'Бокалы и аксессуары для бара': 'bokaly-i-aksessuary-dla-bara-13151/',
    'Посуда для чая и кофе': 'posuda-dla-caa-i-kofe-13165/',
    'Столовые приборы': 'stolovye-pribory-13173/',
    'Все для чистоты и порядка': 'vse-dla-cistoty-i-poradka-13274/',
    'Хранение и консервация': 'hranenie-i-konservacia-13228/',
    'Текстиль для дома': 'tekstil-dla-doma-13233/',
    'Товары для пикника': 'tovary-dla-piknika-13244/',
    'Все для детей': 'vse-dla-detej-13252/',
    'Товары для сада': 'tovary-dla-sada-13356/'
}

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def parse_section(section_url):
    full_url = f"https://williams-oliver.ru/catalog/{section_url}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(full_url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title = soup.find('h1')
        section_name = title.text.strip() if title else "Раздел"
        
        cards = soup.find_all('a', class_='products-list-item')
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
        
        if not products:
            return None
        
        total = len(products)
        online_count = sum(1 for p in products if p['online'])
        prices = [p['price'] for p in products]
        online_prices = [p['price'] for p in products if p['online']]
        
        return {
            'name': section_name,
            'total': total,
            'online': online_count,
            'avg_price': sum(prices) / len(prices),
            'avg_online': sum(online_prices) / len(online_prices) if online_prices else 0,
            'min_price': min(prices),
            'max_price': max(prices)
        }
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
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
        
        if text == '/start':
            keyboard = {
                'keyboard': [[s] for s in SECTIONS.keys()],
                'resize_keyboard': True
            }
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
                result += f"• Средняя цена онлайн: {int(stats['avg_online']):,} ₽\n".replace(',', ' ')
                result += f"• Мин. цена: {int(stats['min_price']):,} ₽\n".replace(',', ' ')
                result += f"• Макс. цена: {int(stats['max_price']):,} ₽".replace(',', ' ')
                send_telegram_message(chat_id, result)
            else:
                send_telegram_message(chat_id, "❌ Не удалось получить данные. Попробуйте позже.")
        
        return 'ok'
    except Exception as e:
        print(f"Ошибка webhook: {e}")
        return 'error'

if __name__ == '__main__':
    app.run()
