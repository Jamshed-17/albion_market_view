import json

def fetch_item_names():
    try:
        with open("data/items.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        mapping = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            uid = item.get("UniqueName")  # именно так в твоём JSON
            localized = item.get("LocalizedNames")
            if not isinstance(localized, dict):
                localized = {}
            ru_name = localized.get("RU-RU")
            if uid and ru_name:
                # Основной ID
                mapping[uid] = ru_name
                # Базовый ID без @X (если там есть @X, хотя в твоём примере его нет)
                base_id = uid.split("@")[0]
                if base_id not in mapping:
                    mapping[base_id] = ru_name
        return mapping
    except Exception as e:
        print("❌ Не удалось открыть локальный файл items.json:", e)
        return {}

print(fetch_item_names())
