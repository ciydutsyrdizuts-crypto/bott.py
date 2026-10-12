# -*- coding: utf-8 -*-
"""speed_boost.py — تسريع البوت بدون تعديل باقي الكود"""
import time
import threading
from collections import OrderedDict


# 1) UVLOOP
def install_uvloop():
    try:
        import uvloop
        uvloop.install()
        print("✅ uvloop installed")
        return True
    except Exception as e:
        print(f"⚠️ uvloop: {e}")
        return False


# 2) كاش اسم البوت
_bot_name_cache = {"value": None, "expire": 0}
_bot_name_lock = threading.Lock()

def get_cached_bot_name(redis_client, hmshelp, ttl=60):
    now = time.time()
    with _bot_name_lock:
        if _bot_name_cache["value"] and _bot_name_cache["expire"] > now:
            return _bot_name_cache["value"]
    try:
        name = redis_client.get(f'{hmshelp}:BotName') or "مشاعر"
        if isinstance(name, bytes):
            name = name.decode('utf-8', 'ignore')
    except Exception:
        name = _bot_name_cache["value"] or "مشاعر"
    with _bot_name_lock:
        _bot_name_cache["value"] = name
        _bot_name_cache["expire"] = now + ttl
    return name

def invalidate_bot_name():
    with _bot_name_lock:
        _bot_name_cache["value"] = None
        _bot_name_cache["expire"] = 0


# 3) كاش بسيط TTL
class TTLCache:
    def __init__(self, max_size=2000, ttl=30):
        self.max_size = max_size
        self.ttl = ttl
        self.store = OrderedDict()
        self.lock = threading.Lock()
    def get(self, key):
        now = time.time()
        with self.lock:
            item = self.store.get(key)
            if not item: return None
            value, expire = item
            if expire < now:
                del self.store[key]; return None
            self.store.move_to_end(key)
            return value
    def set(self, key, value, ttl=None):
        now = time.time()
        t = ttl if ttl is not None else self.ttl
        with self.lock:
            self.store[key] = (value, now + t)
            self.store.move_to_end(key)
            if len(self.store) > self.max_size:
                self.store.popitem(last=False)
    def clear(self):
        with self.lock:
            self.store.clear()

_mute_cache = TTLCache(max_size=10000, ttl=10)

def cached_mute_check(redis_client, user_id, chat_id, hmshelp):
    key = (user_id, chat_id)
    val = _mute_cache.get(key)
    if val is not None: return val
    try:
        muted = bool(redis_client.get(f'{user_id}:mute:{chat_id}{hmshelp}')) or \
                bool(redis_client.get(f'{user_id}:mute:{hmshelp}'))
    except Exception:
        muted = False
    _mute_cache.set(key, muted)
    return muted


# 4) طابور تأجيل المهام (لعدّ الرسائل)
import queue
_deferred_queue = queue.Queue(maxsize=10000)
_deferred_stop = threading.Event()

def _deferred_worker():
    while not _deferred_stop.is_set():
        try:
            task = _deferred_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        if task is None: break
        try: task()
        except Exception as e: print(f"DEFERRED_ERR: {e}")
        finally: _deferred_queue.task_done()

def start_deferred_workers(count=4):
    for i in range(count):
        threading.Thread(target=_deferred_worker, daemon=True, name=f"deferred-{i}").start()
    print(f"✅ {count} deferred workers")

def defer(func):
    try: _deferred_queue.put_nowait(func)
    except queue.Full: pass


# 5) التنشيط
def activate_all():
    install_uvloop()
    start_deferred_workers(count=4)
    print("🚀 Speed Boost Activated")
