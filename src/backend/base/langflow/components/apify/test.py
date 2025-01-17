from apify_client import ApifyClient
import os
from pprint import pprint
import json

token = os.getenv("APIFY_TOKEN")

client = ApifyClient(token=token)

actor = client.actor("apify/google-search-scraper")
info = actor.get()

pprint(info['defaultRunOptions'])
pprint(info['taggedBuilds'])

build = client.build("gfABKIpt72oKlrfgj")
print(json.dumps(build.get(), indent=4, default=lambda o: 'n/a'))
