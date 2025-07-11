from flask import Flask, render_template, request, jsonify
import requests
import plotly.graph_objs as go
from plotly.utils import PlotlyJSONEncoder
import json
import time
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)
executor = ThreadPoolExecutor(4)

@app.template_filter('number_format')
def number_format(value, decimal_places=0):
    try:
        value = float(value)
        return f"{value:,.{decimal_places}f}".replace(",", " ").replace(".", ",")
    except:
        return value

CITIES = ['Bridgewatch', 'Caerleon', 'Fort Sterling', 'Lymhurst', 'Martlock', 'Thetford', 'Black Market']
TAX_RATE = 0.05
MIN_PROFIT = 1000
MAX_ITEMS = 500

ITEM_CATEGORIES = {
    'EQUIPMENT': ['HEAD', 'ARMOR', 'SHOES', 'BAG', 'CAPE'],
    'WEAPONS': ['SWORD', 'AXE', 'MACE', 'DAGGER', 'STAFF', 'BOW', 'CROSSBOW'],
    'RESOURCES': ['ORE', 'WOOD', 'HIDE', 'FIBER', 'ROCK', 'METALBAR', 'PLANK', 'LEATHER', 'CLOTH'],
    'CONSUMABLES': ['POTION', 'FOOD']
}

def generate_item_list():
    items = []
    for category, subcategories in ITEM_CATEGORIES.items():
        for subcat in subcategories:
            for tier in range(4, 8):
                items.append(f'T{tier}_{subcat}')
                if tier > 4:
                    for enchant in range(1, 4):
                        items.append(f'T{tier}_{subcat}@{enchant}')
    return items[:MAX_ITEMS]

ALL_ITEMS = generate_item_list()
ITEM_NAME_MAP = {}

def fetch_item_names():
    url = "https://raw.githubusercontent.com/broderickhyman/ao-bin-dumps/master/formatted/items.json"
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        mapping = {}
        for item in data:
            uid = item.get("Name") or item.get("uniqueName") or item.get("ItemId")
            # здесь поле с русской локализацией может быть в item['LocalizedNames']['RU']
            ru = item.get("LocalizedNames", {}).get("RU") or item.get("LocalizableName_RU")
            if uid and ru:
                mapping[uid] = ru
                base = uid.split('@')[0]
                mapping.setdefault(base, ru)
        return mapping
    except Exception as e:
        print("Не удалось скачать metadata items:", e)
        return {}

@lru_cache(maxsize=1000)
def get_item_prices(item_id):
    url = f"https://europe.albion-online-data.com/api/v2/stats/prices/{item_id}.json"
    try:
        response = requests.get(url, timeout=10)
        time.sleep(0.2)
        return response.json() if response.status_code == 200 else None
    except:
        return None

def analyze_item(item_id, min_profit=1000):
    prices = get_item_prices(item_id)
    if not prices:
        return None

    city_data = {city: {'buy': None, 'sell': None} for city in CITIES}

    for price in prices:
        city = price.get('city')
        if city in CITIES:
            if price.get('sell_price_min'):
                city_data[city]['sell'] = price['sell_price_min']
            if price.get('buy_price_max'):
                city_data[city]['buy'] = price['buy_price_max']

    deals = []
    for buy_city, buy_data in city_data.items():
        for sell_city, sell_data in city_data.items():
            if buy_data['sell'] and sell_data['buy'] and sell_data['buy'] > buy_data['sell']:
                profit = sell_data['buy'] - buy_data['sell']
                profit_after_tax = profit * (1 - TAX_RATE)
                roi = (profit / buy_data['sell']) * 100

                if profit_after_tax >= min_profit:
                    deals.append({
                        'item_id': item_id,
                        'item_name': ITEM_NAME_MAP.get(item_id, item_id),
                        'buy_city': buy_city,
                        'buy_price': buy_data['sell'],
                        'sell_city': sell_city,
                        'sell_price': sell_data['buy'],
                        'profit': profit,
                        'profit_after_tax': profit_after_tax,
                        'roi': roi
                    })

    deals.sort(key=lambda x: x['profit_after_tax'], reverse=True)
    return deals[:10] if deals else None

def find_best_deals():
    best_deals = []
    lock = threading.Lock()

    def process_item(item):
        deals = analyze_item(item, MIN_PROFIT)
        if deals:
            with lock:
                best_deals.extend(deals)

    list(executor.map(process_item, ALL_ITEMS))
    best_deals_sorted = sorted(best_deals, key=lambda x: x['profit_after_tax'], reverse=True)

    for deal in best_deals_sorted:
        deal['item_name'] = ITEM_NAME_MAP.get(deal['item_id'], deal['item_id'])

    return best_deals_sorted[:100]

@app.route('/')
def index():
    return render_template('index.html', items=ALL_ITEMS[:50], ITEM_NAME_MAP=ITEM_NAME_MAP)



@app.route('/analyze', methods=['POST'])
def analyze():
    item_id = request.form.get('item_id')
    min_profit = int(request.form.get('min_profit', 1000))

    deals = analyze_item(item_id, min_profit)
    if not deals:
        return render_template('index.html', items=ALL_ITEMS, ITEM_NAME_MAP=ITEM_NAME_MAP,
                               error=f"Нет выгодных сделок для {item_id}")

    prices = get_item_prices(item_id)
    city_data = {city: {'buy': None, 'sell': None} for city in CITIES}
    for price in prices:
        city = price.get('city')
        if city in CITIES:
            if price.get('sell_price_min'):
                city_data[city]['sell'] = price['sell_price_min']
            if price.get('buy_price_max'):
                city_data[city]['buy'] = price['buy_price_max']

    plot_json = create_price_plot({'item_id': item_id, 'city_data': city_data})
    return render_template('single_item.html',
                           item_id=item_id,
                           item_name=ITEM_NAME_MAP.get(item_id, item_id),
                           deals=deals,
                           plot_json=plot_json,
                           min_profit=min_profit)


@app.route('/best-deals')
def best_deals():
    deals = find_best_deals()
    return render_template('best_deals.html', deals=deals, ITEM_NAME_MAP=ITEM_NAME_MAP)


def create_price_plot(item_data):
    cities = []
    sell_prices = []
    buy_prices = []

    for city, data in item_data['city_data'].items():
        if data['sell'] or data['buy']:
            cities.append(city)
            sell_prices.append(data['sell'] if data['sell'] else None)
            buy_prices.append(data['buy'] if data['buy'] else None)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=cities,
        y=sell_prices,
        name='Цена покупки (min)',
        marker_color='rgb(214, 39, 40)',
        opacity=0.8
    ))

    fig.add_trace(go.Bar(
        x=cities,
        y=buy_prices,
        name='Цена продажи (max)',
        marker_color='rgb(44, 160, 44)',
        opacity=0.8
    ))

    fig.update_layout(
        title=f'Цены для {item_data["item_id"]}',
        xaxis_title='Город',
        yaxis_title='Цена (серебро)',
        barmode='group',
        hovermode='x unified',
        plot_bgcolor='rgba(245, 246, 249, 1)',
        margin=dict(l=40, r=30, t=80, b=40),
        height=400
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)

if __name__ == '__main__':
    ITEM_NAME_MAP = fetch_item_names()
    port = 5000
    while True:
        try:
            app.run(debug=True, port=port)
        except:
            port += 1
