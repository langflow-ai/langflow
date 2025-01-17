from .ericsson_charger import EricssonCharger
from .ericsson_cbio import EricssonBilling

__all__ = [
    "EricssonCharger",
    "EricssonBilling",
]

build_config = {
    "display_name": "Ericsson",
    "name": "ericsson",
    "icon": "Ericsson",
    "components": __all__
}