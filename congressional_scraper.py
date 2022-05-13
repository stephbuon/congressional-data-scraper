import argparse
from typing import Optional

BASE_URL = 'https://congress.gov'
SEARCH_URL = f'{BASE_URL}/search'

from urllib.parse import quote_plus, urlencode
import json
import requests

from bs4 import BeautifulSoup

import speaker_scraper


def create_query(search_term: str, congress: Optional[str] = None):
    q = {
        "source": "congrecord",
        "search": search_term,
    }

    if congress is not None:
        q["congress"] = int(congress)

    return json.dumps(q)


def scrape_search_results(search_term):
    url_params = {
        'q': create_query(search_term),
        'pageSize': 100,
        'page': 1,
    }
    url = f'{SEARCH_URL}?{urlencode(url_params)}'
    print(f'Search url: {url}')

    response = requests.get(url)
    print('Parsing search page...')
    page = BeautifulSoup(response.text, 'html.parser')
    body = page.body
    search_results = body.find_all('span', class_='congressional-record-heading')
    print('Number of results: %d' % len(search_results))

    for result in search_results:
        tag = result.find('a')
        result_href = tag.get('href')
        scrape_record(f'{BASE_URL}{result_href}')

def scrape_record(url):
    response = requests.get(url)
    page = BeautifulSoup(response.text, 'html.parser')
    txt_link_parent = page.find('li', class_='full-text-link')
    txt_link = next(txt_link_parent.children).get('href')
    print(f'Fetching record from {BASE_URL}{txt_link}...')

    response = requests.get(f'{BASE_URL}{txt_link}')
    page = BeautifulSoup(response.text, 'html.parser')

    record_text = page.find('pre').text
    for match in speaker_scraper.scrape(record_text):
        print(match)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('search',
                        help='Return congressional records containing this term.')
    # parser.add_argument('-fy', '--start_year',
    #                     help='The starting date in your date range (it does not matter if the larger or smaller year comes first).')
    # parser.add_argument('-ly', '--end_year',
    #                     help='The ending date in your date range (it does not matter if the smaller or larger year comes first).')

    try:
       args = parser.parse_args()
    except IndexError:
       exit('Congressional Data Scraper takes three arguments: search term, first year, last year. Please see github.com/stephbuon/congressional-data-scraper for more information')

    scrape_search_results(args.search)
