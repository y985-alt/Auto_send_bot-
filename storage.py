import json
import os
import threading

from config import DATA_FILE

_lock = threading.Lock()


def _ensure_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, indent=4)


def load_data():
    _ensure_file()

    with _lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"users": {}}


def save_data(data):
    with _lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)


def get_user(user_id: int):
    data = load_data()

    uid = str(user_id)

    if uid not in data["users"]:
        data["users"][uid] = {
            "state": 0,
            "current_main": None,
            "mappings": {}
        }
        save_data(data)

    return data["users"][uid]


def update_state(user_id: int, state: int):
    data = load_data()

    uid = str(user_id)

    if uid not in data["users"]:
        data["users"][uid] = {
            "state": state,
            "current_main": None,
            "mappings": {}
        }
    else:
        data["users"][uid]["state"] = state

    save_data(data)


def set_current_main(user_id: int, chat_id: int):
    data = load_data()

    uid = str(user_id)

    if uid not in data["users"]:
        get_user(user_id)
        data = load_data()

    data["users"][uid]["current_main"] = str(chat_id)

    save_data(data)


def get_current_main(user_id: int):
    user = get_user(user_id)
    return user.get("current_main")


def add_main_channel(user_id: int, chat_id: int):
    data = load_data()

    uid = str(user_id)

    if uid not in data["users"]:
        get_user(user_id)
        data = load_data()

    mappings = data["users"][uid]["mappings"]

    if str(chat_id) not in mappings:
        mappings[str(chat_id)] = []

    save_data(data)


def add_duplicate_channel(user_id: int, main_chat: int, duplicate_chat: int):
    data = load_data()

    uid = str(user_id)

    if uid not in data["users"]:
        get_user(user_id)
        data = load_data()

    mappings = data["users"][uid]["mappings"]

    if str(main_chat) not in mappings:
        mappings[str(main_chat)] = []

    if duplicate_chat not in mappings[str(main_chat)]:
        mappings[str(main_chat)].append(duplicate_chat)

    save_data(data)


def remove_duplicate_channel(user_id: int, main_chat: int, duplicate_chat: int):
    data = load_data()

    uid = str(user_id)

    try:
        data["users"][uid]["mappings"][str(main_chat)].remove(duplicate_chat)
    except Exception:
        pass

    save_data(data)


def remove_main_channel(user_id: int, main_chat: int):
    data = load_data()

    uid = str(user_id)

    try:
        del data["users"][uid]["mappings"][str(main_chat)]
    except Exception:
        pass

    save_data(data)


def get_duplicates(user_id: int, main_chat: int):
    user = get_user(user_id)

    return user["mappings"].get(str(main_chat), [])


def get_all_mappings(user_id: int):
    user = get_user(user_id)

    return user["mappings"]


def get_every_mapping():
    data = load_data()

    result = {}

    for uid, user in data["users"].items():
        result[uid] = user.get("mappings", {})

    return result


def channel_exists(user_id: int, main_chat: int):
    user = get_user(user_id)

    return str(main_chat) in user["mappings"]


def duplicate_exists(user_id: int, main_chat: int, duplicate_chat: int):
    user = get_user(user_id)

    if str(main_chat) not in user["mappings"]:
        return False

    return duplicate_chat in user["mappings"][str(main_chat)]


def clear_state(user_id: int):
    data = load_data()

    uid = str(user_id)

    if uid in data["users"]:
        data["users"][uid]["state"] = 0
        data["users"][uid]["current_main"] = None

    save_data(data)
