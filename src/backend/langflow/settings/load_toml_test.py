from pprint import pprint

import toml
from toml.decoder import TomlDecodeError

toml_file = "src/backend/langflow/core/agents.toml"

try:
    with open(toml_file) as toml_tile:
        data = toml.load(toml_tile)
except TomlDecodeError as err:
    print(f"{str(err) = }")


x = 1

pprint(f"{data = }")
