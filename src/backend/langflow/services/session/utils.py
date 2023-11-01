import random
import string


def session_id_generator(size=6):
    return "".join(
        random.SystemRandom().choices(string.ascii_uppercase + string.digits, k=size)
    )
