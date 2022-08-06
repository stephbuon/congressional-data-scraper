import argparse
import time
from typing import Optional, List

BASE_URL = 'https://congress.gov'
SEARCH_URL = f'{BASE_URL}/search'
PAGE_SIZE = 100
DEFAULT_CONGRESS = list(range(105, 117 + 1))
DEFAULT_RETRY_DELAY = 100

TOO_MANY_REQUESTS = 429

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


def fetch_retry_time(response: requests.Response):
    retry_time = response.headers.get('Retry-After', None)
    if retry_time is None:
        print('No retry time header, using default.')
        retry_time = DEFAULT_RETRY_DELAY
    else:
        try:
            retry_time = int(retry_time)
            print('Retry-After time from API is: %d' % retry_time)
        except ValueError:
            print('Failed to parse retry time header, using default.')
            retry_time = DEFAULT_RETRY_DELAY
    return retry_time


def scrape_search_results(search_term, max_results, page_num=1, retries=3):
    url_params = {
        'q': create_query(search_term, congress=DEFAULT_CONGRESS),
        'pageSize': PAGE_SIZE,
        'page': page_num,
    }
    url = f'{SEARCH_URL}?{urlencode(url_params)}'
    print(f'Search url: {url}')
    print('Page number is: %d' % page_num)

    response = requests.get(url)

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print('Failed to fetch initial search url. Reason: ' + str(e))
        if retries and response.status_code == TOO_MANY_REQUESTS:
            retry_time = fetch_retry_time(response)
            time.sleep(retry_time)
            yield from scrape_search_results(search_term, max_results,  page_num=page_num, retries=retries - 1)
        elif retries:
            print('Retrying...')
            time.sleep(DEFAULT_RETRY_DELAY)
            yield from scrape_search_results(search_term, max_results, page_num=page_num, retries=retries - 1)
        else:
            print('Out of retries, skipping page...')
        return

    print('Parsing search page...')
    page = BeautifulSoup(response.text, 'html.parser')
    body = page.body
    search_results = body.find_all('span', class_='congressional-record-heading')
    print('Number of results: %d' % len(search_results))

    for search_result_span in search_results:
        tag = search_result_span.find('a')
        result_href = tag.get('href')
        try:
            yield from scrape_record(f'{BASE_URL}{result_href}')
        except StopIteration:
            continue
        except RuntimeError:
            continue
        max_results -= 1
        if not max_results:
            break
    #
    # if max_results and search_results:
    #     print('Continuing to next page...')
    #     yield from scrape_search_results(search_term, page_num + 1, max_results)


def scrape_record(url, retries=3):
    print('scrape_record', url)
    response = requests.get(url)

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print('Failed to scrape record. Reason: ' + str(e))
        if retries and response.status_code == TOO_MANY_REQUESTS:
            retry_time = fetch_retry_time(response)
            time.sleep(retry_time)
            yield from scrape_record(url, retries=retries - 1)
        elif retries:
            print('Retrying...')
            time.sleep(DEFAULT_RETRY_DELAY)
            yield from scrape_record(url, retries=retries - 1)
        else:
            print('Out of retries, skipping record...')
        return

    page = BeautifulSoup(response.text, 'html.parser')
    main_wrapper = page.find('div', class_='main-wrapper')

    if main_wrapper is None:
        print('Failed to fetch record.')
        raise StopIteration

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
        raise StopIteration
    txt_link = next(txt_link_parent.children).get('href')
    yield from scrape_txt_record(txt_link, url, date, title)


def scrape_txt_record(txt_link, record_url, record_date, record_title, retries=3):
    print(f'Fetching record from {BASE_URL}{txt_link}...')

    response = requests.get(f'{BASE_URL}{txt_link}')

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print('Failed to scrape TXT record link. Reason: ' + str(e))
        if retries and response.status_code == TOO_MANY_REQUESTS:
            retry_time = fetch_retry_time(response)
            time.sleep(retry_time)
            yield from scrape_txt_record(txt_link, record_url, record_date, record_title, retries=retries - 1)
        elif retries:
            print('Retrying...')
            time.sleep(DEFAULT_RETRY_DELAY)
            yield from scrape_txt_record(txt_link, record_url, record_date, record_title, retries=retries - 1)
        else:
            print('Out of retries, skipping TXT data...')
        return

    page = BeautifulSoup(response.text, 'html.parser')

    record_text = page.find('pre')
    if record_text is None:
        print(f'Failed to find record text on link: {BASE_URL}{txt_link} . Skipping...')
        raise StopIteration
    record_text = record_text.text

    for speaker, text in speaker_scraper.scrape(record_text):
        yield record_url, record_date, record_title, speaker, text


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('search_term',
                        help='Return congressional records containing this term.')
    parser.add_argument('output_file',
                        help='Return congressional records containing this term.')
    parser.add_argument('-r', '--result-count',
                        help='Max number of results you want',
                        default=9000, type=int, nargs='?')
    # parser.add_argument('-fy', '--start_year',
    #                     help='The starting date in your date range (it does not matter if the larger or smaller year comes first).')
    # parser.add_argument('-ly', '--end_year',
    #                     help='The ending date in your date range (it does not matter if the smaller or larger year comes first).')
    args = parser.parse_args()
    max_result_count = args.result_count
    page_count = 0
    total_result_count = 0

    # Reset/create file
    with open(args.output_file, 'w+') as f:
        pass

    while max_result_count:
        num_page_results = 0
        page_results = []
        page_count += 1
        for result in scrape_search_results(args.search_term, max_result_count, page_num=page_count):
            if result is None:
                continue
            url, date, title, speaker, text = result
            text = text.replace('\n', ' ').replace('\t', ' ')
            page_results.append({"url": url, "date": date, "title": title, "speaker": speaker, "text": text})
            num_page_results += 1
            max_result_count -= 1

            if not max_result_count:
                break

        if not num_page_results:
            break

        df = pd.DataFrame(page_results)
        df.set_index("url", inplace=True)
        df.to_csv(args.output_file, sep='|', mode='a', header=page_count == 1)

        total_result_count += num_page_results

    print('Scraped: %d pages, %d individual records.' % (page_count, total_result_count))