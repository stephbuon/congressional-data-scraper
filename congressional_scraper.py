import argparse
import time
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from typing import Optional, List
import speaker_scraper  # Ensure this module is available
import sys
import logging
import csv  # Import csv module for quoting

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Constants
API_KEY = 'DEMO_KEY'  # Replace with your actual API key
BASE_API_URL = 'https://api.govinfo.gov'
CHRG_COLLECTION = 'CHRG'
PAGE_SIZE = 1000  # Max allowed by GovInfo API
RETRY_DELAY = 30  # seconds
MAX_RETRIES = 3

def get_search_results(query: str, page_size: int, offset_mark: Optional[str] = None) -> dict:
    search_url = f"{BASE_API_URL}/search"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    params = {
        'api_key': API_KEY,
        "historical": True
    }
    payload = {
        "query": query,
        "pageSize": page_size,
        "offsetMark": offset_mark if offset_mark else "*",
        "sorts": [
            {
                "field": "dateIssued",
                "sortOrder": "DESC"
            }
        ],
        "resultLevel": "default"
    }

    logging.info(f"Sending POST request to {search_url} with payload: {json.dumps(payload)[:500]}...")  # Truncated for readability

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(search_url, headers=headers, params=params, json=payload)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                logging.warning(f"Rate limited (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            logging.info("Search request successful.")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTPError on attempt {attempt}: {e}")
            logging.error(f"Response Body: {response.text}")  # Log response body for debugging
            if attempt < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("Max retries reached. Exiting search.")
                raise
        except Exception as e:
            logging.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("Max retries reached. Exiting search.")
                raise

def get_granules(package_id: str) -> List[dict]:
    granules_url = f"{BASE_API_URL}/packages/{package_id}/granules"
    params = {
        'api_key': API_KEY,
        'pageSize': PAGE_SIZE,
        'offsetMark': '*'
    }
    granules = []
    while True:
        logging.info(f"Fetching granules from {granules_url} with params {params}")
        try:
            response = requests.get(granules_url, params=params)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                logging.warning(f"Rate limited while fetching granules (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            data = response.json()
            fetched_granules = data.get('granules', [])
            granules.extend(fetched_granules)
            logging.info(f"Fetched {len(fetched_granules)} granules.")
            if 'nextOffsetMark' in data:
                params['offsetMark'] = data['nextOffsetMark']
            else:
                break
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTPError while fetching granules: {e}")
            logging.error(f"Response Body: {response.text}")  # Log response body for debugging
            break
        except Exception as e:
            logging.error(f"Unexpected error while fetching granules: {e}")
            break
    return granules

def get_granule_summary(package_id: str, granule_id: str) -> dict:
    summary_url = f"{BASE_API_URL}/packages/{package_id}/granules/{granule_id}/summary"
    params = {
        'api_key': API_KEY
    }
    logging.info(f"Fetching granule summary from {summary_url}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(summary_url, params=params)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                logging.warning(f"Rate limited while fetching granule summary (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            logging.info("Granule summary fetched successfully.")
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTPError on attempt {attempt} while fetching granule summary: {e}")
            logging.error(f"Response Body: {response.text}")  # Log response body for debugging
            if attempt < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("Max retries reached for granule summary. Skipping this granule.")
                return {}
        except Exception as e:
            logging.error(f"Unexpected error on attempt {attempt} while fetching granule summary: {e}")
            if attempt < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("Max retries reached for granule summary. Skipping this granule.")
                return {}

def get_htm_content(package_id: str, granule_id: str) -> str:
    htm_url = f"{BASE_API_URL}/packages/{package_id}/granules/{granule_id}/htm"
    params = {
        'api_key': API_KEY
    }
    logging.info(f"Fetching HTM content from {htm_url}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(htm_url, params=params)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                logging.warning(f"Rate limited while fetching HTM content (429). Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            logging.info("HTM content fetched successfully.")
            return response.text
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTPError on attempt {attempt} while fetching HTM content: {e}")
            logging.error(f"Response Body: {response.text}")  # Log response body for debugging
            if attempt < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("Max retries reached for HTM content. Skipping this granule.")
                return ""
        except Exception as e:
            logging.error(f"Unexpected error on attempt {attempt} while fetching HTM content: {e}")
            if attempt < MAX_RETRIES:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("Max retries reached for HTM content. Skipping this granule.")
                return ""

def process_speech(record_url: str, record_date: str, record_title: str, htm_content: str):
    soup = BeautifulSoup(htm_content, 'html.parser')
    pre_tag = soup.find('pre')
    if not pre_tag:
        logging.warning(f"No <pre> tag found in {record_url}. Skipping...")
        return []
    record_text = pre_tag.get_text()
    speeches = speaker_scraper.scrape(record_text)
    processed_speeches = []
    for speaker, text in speeches:
        text = text.replace('\n', ' ').replace('\t', ' ').strip()
        processed_speeches.append({
            "url": record_url,
            "date": record_date,
            "title": record_title,
            "speaker": speaker,
            "text": text
        })
    return processed_speeches

def main(output_file: str, max_results: Optional[int]):
    #query = f"collection:{CHRG_COLLECTION} AND dateIssued:[2000-01-01 TO 2001-01-01]"
    query = f"collection:{CHRG_COLLECTION}"
    offset_mark = None
    total_results = 0

    # Initialize CSV with header using comma delimiter
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["url", "date", "title", "speaker", "text"], delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writeheader()

    while True:
        try:
            search_data = get_search_results(query, PAGE_SIZE, offset_mark)
        except Exception as e:
            logging.error(f"Error during search: {e}")
            break

        results = search_data.get('results', [])
        if not results:
            logging.info("No more results found.")
            break

        for result in results:
            package_id = result.get('packageId')
            if not package_id:
                logging.warning("No packageId found in result. Skipping...")
                continue
            granules = get_granules(package_id)
            for granule in granules:
                granule_id = granule.get('granuleId')
                if not granule_id:
                    logging.warning(f"No granuleId found in granule: {granule}. Skipping...")
                    continue
                summary = get_granule_summary(package_id, granule_id)
                if not summary:
                    logging.warning(f"No summary available for granule {granule_id}. Skipping...")
                    continue
                record_title = summary.get('title', '').replace('\n', ' ').strip()
                record_date = summary.get('dateIssued', '').strip()
                htm_content = get_htm_content(package_id, granule_id)
                if not htm_content:
                    logging.warning(f"No HTM content for granule {granule_id}. Skipping...")
                    continue
                record_url = f"{BASE_API_URL}/packages/{package_id}/granules/{granule_id}/htm"
                speeches = process_speech(record_url, record_date, record_title, htm_content)
                if speeches:
                    # Append to CSV using csv.DictWriter
                    with open(output_file, 'a', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=["url", "date", "title", "speaker", "text"], delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
                        for speech in speeches:
                            writer.writerow(speech)
                    total_results += len(speeches)
                    logging.info(f"Total speeches collected: {total_results}")
                    if max_results and total_results >= max_results:
                        logging.info("Reached maximum number of results specified.")
                        return
        # Update offset_mark for next iteration
        offset_mark = search_data.get('nextOffsetMark')
        if not offset_mark:
            logging.info("No more pages to fetch.")
            break

    logging.info(f"Scraping complete. Total speeches collected: {total_results}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch congressional speeches from GovInfo API.')
    parser.add_argument('output_file', help='Path to the output CSV file.')
    parser.add_argument('--max-results', type=int, default=None,
                        help='Maximum number of speeches to fetch. Default is all available.')
    args = parser.parse_args()

    try:
        main(args.output_file, args.max_results)
    except KeyboardInterrupt:
        logging.info("\nProcess interrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)
