from .csg_ussd import CsgUssd

__all__ = [
    "CsgUssd",
]

build_config = {
    "display_name": "CSG",
    "name": "csg",
    "icon": "csg",
    "components": __all__
}