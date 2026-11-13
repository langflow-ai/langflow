import numpy as np

MAX_TEXT_LENGTH = 6000
MAX_ITEMS_LENGTH = 1000

# numpy scalars/arrays (e.g. MMR similarity scores) are not handled by jsonable_encoder or orjson by default
NUMPY_ENCODERS = {np.generic: lambda value: value.item(), np.ndarray: lambda value: value.tolist()}
