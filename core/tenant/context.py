import threading

_thread_locals = threading.local()


def set_current_plant(plant):
    _thread_locals.plant = plant


def get_current_plant():
    return getattr(_thread_locals, "plant", None)


def clear_current_plant():
    if hasattr(_thread_locals, "plant"):
        del _thread_locals.plant