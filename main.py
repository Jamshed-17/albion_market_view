import requests
from termcolor import colored

# Получение информации о ценах в обычных городах и на черном рынке
def get_item_prices(item_id):
    url = f"https://europe.albion-online-data.com/api/v2/stats/prices/{item_id}.json"
    response = requests.get(url)

    if response.status_code == 200:
        prices = response.json()

        # Фильтрация городов с доступными ценами для покупки и продажи
        buy_opportunities = []
        sell_opportunities = []

        for price_info in prices:
            city = price_info.get('city')
            sell_price = price_info.get('sell_price_min', None)  # Цена продажи
            buy_price = price_info.get('buy_price_max', None)    # Цена покупки

            if sell_price:
                buy_opportunities.append({'city': city, 'price': sell_price})
            if buy_price:
                sell_opportunities.append({'city': city, 'price': buy_price})

        # Поиск всех выгодных сделок
        profitable_deals = []
        for buy_opportunity in buy_opportunities:
            for sell_opportunity in sell_opportunities:
                if sell_opportunity['price'] > buy_opportunity['price']:
                    profit = sell_opportunity['price'] - buy_opportunity['price']
                    profitable_deals.append({
                        'buy_city': buy_opportunity['city'],
                        'buy_price': buy_opportunity['price'],
                        'sell_city': sell_opportunity['city'],
                        'sell_price': sell_opportunity['price'],
                        'profit': profit
                    })

        # Вывод всех выгодных сделок
        if profitable_deals:
            for deal in profitable_deals:
                print(f"Вы можете купить в {colored(deal['buy_city'], 'yellow')} предмет {colored(item_id, 'blue')} за {colored(deal['buy_price'], 'magenta')} монет "
                      f"и продать его в {colored(deal['sell_city'], 'yellow')} за {colored(deal['sell_price'], 'green')} монет, "
                      f"получив выручку в {colored(deal['profit'], 'green')} монет.")
        else:
            print("Не удалось найти выгодные сделки.")
    else:
        print("Ошибка получения данных с API")



# Пример использования: замени 'T4_BAG' на нужный ID предмета
item_id = 'T4_BAG'  # ID предмета
get_item_prices(item_id)         # Данные о ценах в городах
