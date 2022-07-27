import argparse
from typing import Optional, List

BASE_URL = 'https://congress.gov'
SEARCH_URL = f'{BASE_URL}/search'
PAGE_SIZE = 100
DEFAULT_CONGRESS = list(range(105, 117 + 1))

from urllib.parse import quote_plus, urlencode
import json
import requests

from bs4 import BeautifulSoup

import speaker_scraper

import pandas as pd
from datetime import datetime


# todo: ADD DATE and TITLE

def create_query(search_term: str, congress: Optional[List[str]] = None):
    q = {
        "source": "congrecord",
        "search": search_term,
    }

    if congress is not None:
        q["congress"] = congress

    return json.dumps(q)


def scrape_search_results(search_term, page_num=1, max_results=9999):
    url_params = {
        'q': create_query(search_term, congress=DEFAULT_CONGRESS),
        'pageSize': PAGE_SIZE,
        'page': page_num,
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
        yield from scrape_record(f'{BASE_URL}{result_href}')
        max_results -= 1
        if not max_results:
            break

    if max_results and search_results:
        print('Continuing to next page...')
        yield from scrape_search_results(search_term, page_num + 1, max_results)


def scrape_record(url):
    print('scrape_record', url)
    response = requests.get(url)
    page = BeautifulSoup(response.text, 'html.parser')
    main_wrapper = page.find('div', class_='main-wrapper')

    if main_wrapper is None:
        print('Failed to fetch record.')
        return

    title = ''
    date = ''
    title_tag = main_wrapper.find('h2')
    if title_tag:
        title = title_tag.text
        title = title.replace('\n', '')

    subtitle_tag = main_wrapper.find('span', class_='quiet')

    if subtitle_tag:
        parts = subtitle_tag.text.split('-')
        if len(parts) == 2:
            date = parts[1].strip().replace(',', '').replace(')', '')
            date = datetime.strptime(date, '%B %d %Y').strftime('%Y-%m-%d')

    txt_link_parent = page.find('li', class_='full-text-link')
    if txt_link_parent is None:
        print('Couldnt find text link')
        return
    txt_link = next(txt_link_parent.children).get('href')
    print(f'Fetching record from {BASE_URL}{txt_link}...')

    response = requests.get(f'{BASE_URL}{txt_link}')
    page = BeautifulSoup(response.text, 'html.parser')

    record_text = page.find('pre')
    if record_text is None:
        print(f'Failed to find record text on link: {BASE_URL}{txt_link} . Skipping...')
        return
    record_text = record_text.text

    for speaker, text in speaker_scraper.scrape(record_text):
        yield url, date, title, speaker, text


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('search_term',
                        help='Return congressional records containing this term.')
    parser.add_argument('output_file',
                        help='Return congressional records containing this term.')
    # parser.add_argument('-fy', '--start_year',
    #                     help='The starting date in your date range (it does not matter if the larger or smaller year comes first).')
    # parser.add_argument('-ly', '--end_year',
    #                     help='The ending date in your date range (it does not matter if the smaller or larger year comes first).')
    args = parser.parse_args()
    results = []

    for url, date, title, speaker, text in scrape_search_results(args.search_term):
        text = text.replace('\n', ' ').replace('\t', ' ')
        results.append({"url": url, "date": date, "title": title, "speaker": speaker, "text": text})

    df = pd.DataFrame(results)
    df.set_index("url", inplace=True)
    df.to_csv(args.output_file, sep='|')
