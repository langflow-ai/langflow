import covalent as ct
from functools import wraps


def task(ct_type, use_covalent=False):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            # Check for the presence of the environment variable
            if ct_type:
                # Apply the covalent decorator if the variable is present
                decorator = ct.electron if ct_type == "electron" else ct.lattice
                decorated_function = decorator(function)
            else:
                # Don't apply the decorator if the variable is not present
                decorated_function = function
            return decorated_function(*args, **kwargs)

        return wrapper

    return decorator
