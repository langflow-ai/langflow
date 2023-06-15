from pydantic import (
    BaseModel,
    BaseSettings,
    PyObject,
    Field,
)

from pprint import pprint


class SubModel(BaseModel):
    foo = 'bar'
    apple = 1


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    api_key: str = Field(..., env='my_api_key')

    lc: PyObject = 'langchain.embeddings.openai.OpenAIEmbeddings'

    # to override domains:
    # export my_prefix_domains='["foo.com", "bar.com"]'
    domains: set[str] = set()

    # to override more_settings:
    # export my_prefix_more_settings='{"foo": "x", "apple": 1}'
    more_settings: SubModel = SubModel()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

        env_prefix = 'my_prefix_'  # defaults to no prefix, i.e. ""
        fields = {
            'auth_key': {
                'env': 'my_auth_key',
            },
            'redis_dsn': {
                'env': ['service_redis_dsn', 'redis_url']
            }
        }


my_settings = Settings(_env_file='.env')
my_dict = my_settings.dict()

my_object = my_dict['lc']

pprint(my_dict)

print(f'{[my_object.__name__]} - {dir(my_object) = }')

x = 1
