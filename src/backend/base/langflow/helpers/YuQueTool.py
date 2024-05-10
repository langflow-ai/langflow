from typing import List, Dict

import requests


class YuQueCatalog:
    def __init__(self, id: int, title: str, book_id: int):
        self.id = id
        self.title = title
        self.book_id = book_id


base_url = 'https://www.yuque.com'


def get_doc_catalog(team: str, knowledge: str, doc_headers: Dict) -> List[YuQueCatalog]:
    """Get the directory of Yuque knowledge base"""
    url = f'{base_url}/api/v2/repos/{team}/{knowledge}/docs'
    response = requests.get(url, headers=doc_headers)
    json_data = response.json().get("data")

    catalog_list = []
    for item in json_data:
        print(item['id'])
        catalog = YuQueCatalog(
            id=item['id'],
            title=item['title'],
            book_id=item['book_id']
        )
        catalog_list.append(catalog)
    return catalog_list


def get_doc_detail(book_id: int, id: int, doc_headers: Dict):
    """Get details of Yuque knowledge documents"""
    url = f'{base_url}/api/v2/repos/{book_id}/docs/{id}'
    response = requests.get(url, headers=doc_headers)
    return response.json().get("data").get("body")


def get_doc_detail_by_code(token: str, url: str):
    """Get details of a single document based on URL"""
    if url.startswith("/"):
        url = url[1:]
    split_result = url.split("/")
    team = split_result[0]
    knowledge = split_result[1]
    code = split_result[2]
    full_url = f'{base_url}/api/v2/repos/{team}/{knowledge}/docs/{code}'
    doc_headers = {
        'User-Agent': team,
        'X-Auth-Token': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(full_url, headers=doc_headers)
    return response.json().get("data").get("body")


def get_knowledge_detail(token: str, url: str) -> str:
    """Get all document details under Yuque Knowledge Base"""
    if url.startswith("/"):
        url = url[1:]
    split_result = url.split("/")
    team = split_result[0]
    knowledge = split_result[1]
    doc_headers = {
        'User-Agent': team,
        'X-Auth-Token': token,
        'Content-Type': 'application/json'
    }
    catalog = get_doc_catalog(team, knowledge, doc_headers)
    result = ''
    for item in catalog:
        doc = get_doc_detail(item.book_id, item.id, doc_headers)
        result += '\n' + doc
    return result
