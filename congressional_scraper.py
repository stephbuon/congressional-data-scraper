import argparse
import time
from typing import Optional, List, Tuple
import re

BASE_URL = 'https://congress.gov'
SEARCH_URL = f'{BASE_URL}/search'
PAGE_SIZE = 100
DEFAULT_RETRY_DELAY = 610

TOO_MANY_REQUESTS = 429

START_TIME = 0


class EndOfQueryException(Exception):
    pass


from urllib.parse import quote_plus, urlencode
import json
import requests

from bs4 import BeautifulSoup

import speaker_scraper

import pandas as pd
from datetime import datetime


from enum import Enum


class PageSorts(Enum):
    RELEVANCY = 'relevancy'
    ISSUE_DATE_ASCENDING = 'issueAsc'
    ISSUE_DATE_DESCENDING = 'issueDesc'
    TITLE = 'title'


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
        print('No retry time header, using default of %d seconds.' % DEFAULT_RETRY_DELAY)
        retry_time = DEFAULT_RETRY_DELAY
    else:
        try:
            retry_time = int(retry_time)
            print('Retry-After time from API is: %d' % retry_time)
            # Additional buffer time
            retry_time += 3
        except ValueError:
            print('Failed to parse retry time header, using default.')
            retry_time = DEFAULT_RETRY_DELAY
    return retry_time


def scrape_search_results(search_term, max_results, congress: List[int], pageSort: str, page_num=1, retries=3, ):
    url_params = {
        'q': create_query(search_term, congress=congress),
        'pageSize': PAGE_SIZE,
        'page': page_num,
        'pageSort': pageSort
    }
    url = f'{SEARCH_URL}?{urlencode(url_params)}'
    print(f'Search url: {url}')
    print('Page number is: %d' % page_num)
    print('Time elapsed: %f seconds' % (time.time() - START_TIME))

    response = requests.get(url)

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print('Failed to fetch initial search url. Reason: ' + str(e))
        if retries and response.status_code == TOO_MANY_REQUESTS:
            retry_time = fetch_retry_time(response)
            time.sleep(retry_time)
            yield from scrape_search_results(search_term, max_results,  congress, pageSort, page_num=page_num, retries=retries - 1)
        elif retries:
            print('Retrying...')
            time.sleep(DEFAULT_RETRY_DELAY)
            yield from scrape_search_results(search_term, max_results, congress, pageSort, page_num=page_num, retries=retries - 1)
        else:
            print('Out of retries, skipping page...')
        return

    print('Parsing search page...')
    page = BeautifulSoup(response.text, 'html.parser')
    body = page.body
    search_results = body.find_all('span', class_='congressional-record-heading')
    print('Number of results: %d' % len(search_results))

    if not len(search_results):
        raise EndOfQueryException('No results on page %d' % page_num)

    for search_result_span in search_results:
        tag = search_result_span.find('a')
        result_href = tag.get('href')
        scrape_time = time.time()
        try:
            yield from scrape_record(f'{BASE_URL}{result_href}')
        except StopIteration:
            continue
        scrape_time = time.time() - scrape_time
        print('Scrape took: %f seconds' % scrape_time)

        # except RuntimeError:
        #     continue
        max_results[0] -= 1
        if max_results[0] <= 0:
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

    print('Scraping record text for speakers...')
    for speaker, text in speaker_scraper.scrape(record_text):
        yield record_url, record_date, record_title, speaker, text


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('search_term',
                        help='Return congressional records containing this term. '
                             'For multi-word search terms, surround them in double quotation marks.')
    parser.add_argument('output_file',
                        help='Name of the output file')
    parser.add_argument('-r', '--result-count',
                        help='Max number of results you want (default: %(default)s)',
                        default=9000, const=9000, type=int, nargs='?')
    parser.add_argument('--start-congress',
                        help='Beginning congress (inclusive) (default: %(default)s)',
                        default=105, const=105, type=int, nargs='?')
    parser.add_argument('--end-congress',
                        help='End congress (inclusive) (default: %(default)s)',
                        default=117, const=117, type=int, nargs='?')
    parser.add_argument('--default-retry-delay',
                        help='Default retry delay in seconds when an API call fail due to throttling.'
                        '(default: %(default)s)',
                        default=DEFAULT_RETRY_DELAY, const=DEFAULT_RETRY_DELAY, type=int, nargs='?')
    parser.add_argument('--sort',
                        default=PageSorts.ISSUE_DATE_ASCENDING.value,
                        const=PageSorts.ISSUE_DATE_ASCENDING.value,
                        nargs='?',
                        choices=[v.value for v in PageSorts],
                        help='Sort method for search results (default: %(default)s)')

    # parser.add_argument('-fy', '--start_year',
    #                     help='The starting date in your date range (it does not matter if the larger or smaller year comes first).')
    # parser.add_argument('-ly', '--end_year',
    #                     help='The ending date in your date range (it does not matter if the smaller or larger year comes first).')
    args = parser.parse_args()
    max_result_count = [ args.result_count ]  # Must be list to pass by reference
    print('Max results specified: %d' % max_result_count[0])
    page_count = 0
    total_result_count = 0

    DEFAULT_RETRY_DELAY = args.default_retry_delay
    print('Retry delay is %d' % DEFAULT_RETRY_DELAY)

    congress_range = list(range(args.start_congress, args.end_congress + 1))

    # Reset/create file
    with open(args.output_file, 'w+') as f:
        pass

    START_TIME = time.time()

    while max_result_count[0] > 0:
        num_page_results = 0
        page_results = []
        page_count += 1
        old_search_count = max_result_count[0]

        try:
            for result in scrape_search_results(args.search_term, max_result_count, congress=congress_range, pageSort=args.sort, page_num=page_count):
                if result is None:
                    continue
                url, date, title, speaker, text = result
                text = text.replace('\n', ' ').replace('\t', ' ')
                page_results.append({"url": url, "date": date, "title": title, "speaker": speaker, "text": text})
                num_page_results += 1

        except EndOfQueryException as e:
            print(e)

        if page_results:
            df = pd.DataFrame(page_results)
            df.set_index("url", inplace=True)
            df.to_csv(args.output_file, sep='|', mode='a', header=page_count == 1)
        else:
            print('Got 0 speeches for page: %d' % page_count)

        total_result_count += num_page_results

        if max_result_count[0] <= 0:
            break

    print('Scraped: %d pages, %d individual records, %d individual speaker speeches.' % (page_count,
                                                                                 args.result_count - max_result_count[0],
                                                                                 total_result_count))
