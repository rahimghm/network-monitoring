automatic_polling_paused = False


def pause_automatic_polling():
    global automatic_polling_paused
    automatic_polling_paused = True


def resume_automatic_polling():
    global automatic_polling_paused
    automatic_polling_paused = False


def is_automatic_polling_paused() -> bool:
    return automatic_polling_paused
