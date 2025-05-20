import argparse
import os
import sys
import time
import csv
import logging
import threading
from datetime import date, datetime, timedelta
from typing import Optional, List

import requests
from bs4 import BeautifulSoup
import speaker_scraper

# ------------------- Configuration -------------------
BASE_API_URL        = 'https://api.govinfo.gov'
PAGE_SIZE           = 1000
RETRY_DELAY         = 15    # seconds on 429
MAX_RETRIES         = 3
# these get initialized once we see the first rate‐limit header:
RATE_LIMIT_PER_HOUR = None
RATE_INTERVAL       = None   # seconds between calls

# only log headers every N seconds
HEADER_LOG_INTERVAL   = 300.0   # seconds
_last_header_log_time = 0.0
_header_log_lock      = threading.Lock()

# ------------------- Logging Setup -------------------
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[handler]
)

# ------------------- Global state -------------------
rate_lock      = threading.Lock()
last_call_time = 0.0
summary_lock   = threading.Lock()
raw_lock       = threading.Lock()

# Single API key
API_KEY = 'DEMO_KEY'

def get_api_key() -> str:
    return API_KEY

def rate_limit():
    """Sleep as needed to enforce the aggregate calls/hour limit."""
    global last_call_time, RATE_INTERVAL
    if RATE_INTERVAL is None:
        return    # not yet initialized
    with rate_lock:
        now = time.time()
        to_wait = RATE_INTERVAL - (now - last_call_time)
        if to_wait > 0:
            time.sleep(to_wait)
        last_call_time = time.time()

# ------------------- GovInfo Helpers -------------------

def get_search_results(query: str, page_size: int, offset_mark: Optional[str]=None) -> dict:
    global _last_header_log_time, RATE_LIMIT_PER_HOUR, RATE_INTERVAL
    rate_limit()
    url = f"{BASE_API_URL}/search"
    headers = {'Content-Type':'application/json','Accept':'application/json'}
    params  = {'api_key': get_api_key(), 'historical': True}
    payload = {
        'query': query,
        'pageSize': page_size,
        'offsetMark': offset_mark or '*',
        'sorts':[{'field':'publishdate','sortOrder':'DESC'}],
        'resultLevel':'default'
    }

    for attempt in range(1, MAX_RETRIES+1):
        resp = requests.post(url, headers=headers, params=params, json=payload)
        if resp.status_code == 429:
            wait = int(resp.headers.get('Retry-After', RETRY_DELAY))
            logging.warning(f"429 rate limit, sleeping {wait}s…")
            time.sleep(wait)
            continue
        resp.raise_for_status()

        now = time.time()
        with _header_log_lock:
            if now - _last_header_log_time >= HEADER_LOG_INTERVAL:
                limit_hdr     = resp.headers.get('X-RateLimit-Limit')
                remaining_hdr = resp.headers.get('X-RateLimit-Remaining')
                logging.info(f"API rate limit header: limit={limit_hdr}, remaining={remaining_hdr}")
                _last_header_log_time = now
                if limit_hdr:
                    per_key = int(limit_hdr)
                    RATE_LIMIT_PER_HOUR = per_key
                    RATE_INTERVAL = 3600.0 / RATE_LIMIT_PER_HOUR
                    logging.info(f"Rate limit {RATE_LIMIT_PER_HOUR}/hr → interval {RATE_INTERVAL:.3f}s")

        return resp.json()

    raise RuntimeError("Max retries exceeded for search")


def get_granules(package_id: str) -> List[dict]:
    all_g = []
    url   = f"{BASE_API_URL}/packages/{package_id}/granules"
    params= {'api_key': get_api_key(), 'pageSize': PAGE_SIZE, 'offsetMark': '*'}
    while True:
        rate_limit()
        resp = requests.get(url, params=params)
        if resp.status_code == 429:
            wait = int(resp.headers.get('Retry-After', RETRY_DELAY))
            logging.warning(f"429 granules limit, sleeping {wait}s…")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        all_g.extend(data.get('granules', []))
        nxt = data.get('nextOffsetMark')
        if not nxt:
            break
        params['offsetMark'] = nxt
    return all_g


def get_granule_summary(pkg: str, gran: str) -> dict:
    url    = f"{BASE_API_URL}/packages/{pkg}/granules/{gran}/summary"
    params = {'api_key': get_api_key()}
    for attempt in range(1, MAX_RETRIES+1):
        rate_limit()
        resp = requests.get(url, params=params)
        if resp.status_code == 429:
            time.sleep(RETRY_DELAY)
            continue
        try:
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return {}
    return {}


def get_htm(pkg: str, gran: str) -> str:
    url    = f"{BASE_API_URL}/packages/{pkg}/granules/{gran}/htm"
    params = {'api_key': get_api_key()}
    for attempt in range(1, MAX_RETRIES+1):
        rate_limit()
        resp = requests.get(url, params=params)
        if resp.status_code == 429:
            time.sleep(RETRY_DELAY)
            continue
        try:
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return ''
    return ''

# ------------------- Speech Processing -------------------

def extract_pre_text(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, 'html.parser')
    pres  = soup.find_all('pre')
    if not pres:
        return None

    texts = [p.get_text() for p in pres if p.get_text().strip()]
    return "\n\n".join(texts) if texts else None


def process_speeches(url: str, date_str: str, title: str, html: str):
    txt = extract_pre_text(html)
    if not txt:
        return []
    parts = speaker_scraper.scrape(txt)
    out   = []
    for speaker, body in parts:
        clean = body.replace('\n',' ').replace('\t',' ').strip()
        out.append({
            'url':     url,
            'date':    date_str,
            'title':   title,
            'speaker': speaker,
            'text':    clean
        })
    return out

# ------------------- Worker for one day -------------------

def scrape_day(year: int, month: int, day: int, workers: int, output_dir: str):
    d = date(year, month, day)
    day_str = d.isoformat()
    logging.info(f"=== Starting scrape for {day_str} ===")

    query = f"{BASE_QUERY} AND publishdate:range({day_str},{day_str})"
    offset = None
    pkg_ids = set()
    while True:
        try:
            data = get_search_results(query, PAGE_SIZE, offset)
        except Exception as e:
            logging.error(f"Search for {day_str} failed: {e}")
            return
        for res in data.get('results', []):
            pkg = res.get('packageId')
            if pkg:
                pkg_ids.add(pkg)
        offset = data.get('nextOffsetMark')
        if not offset:
            break

    if not pkg_ids:
        logging.info(f"No packages for {day_str} — skipping.")
    else:
        scraped_dir = os.path.join(output_dir, 'scraped_output')
        raw_dir     = os.path.join(output_dir, 'raw_output')
        os.makedirs(scraped_dir, exist_ok=True)
        os.makedirs(raw_dir, exist_ok=True)

        daily_csv  = os.path.join(scraped_dir, f"{day_str}.csv")
        daily_raw  = os.path.join(raw_dir,     f"{day_str}.html")

        def work_pkg(pkg):
            for gran in get_granules(pkg):
                gid = gran.get('granuleId')
                if not gid:
                    continue

                meta  = get_granule_summary(pkg, gid)
                title = meta.get('title','').replace('\n',' ').strip()
                dstr  = meta.get('dateIssued','').strip()
                if not title or not dstr:
                    continue

                try:
                    rec_date = datetime.fromisoformat(dstr).date()
                except ValueError:
                    continue
                if rec_date != d:
                    continue

                url  = f"{BASE_API_URL}/packages/{pkg}/granules/{gid}/htm"
                html = get_htm(pkg, gid)

                with raw_lock:
                    with open(daily_raw, 'a', encoding='utf-8') as rf:
                        rf.write(f"\n\n=== PACKAGE {pkg} | GRANULE {gid} ===\n")
                        rf.write(html)

                speeches = process_speeches(url, dstr, title, html)
                with summary_lock:
                    with open(SUMMARY_CSV, 'a', newline='', encoding='utf-8') as sf:
                        writer = csv.DictWriter(sf, fieldnames=['date','title','has_speech'])
                        writer.writerow({
                            'date':      dstr,
                            'title':     title,
                            'has_speech': bool(speeches)
                        })
                    write_header = not os.path.exists(daily_csv)
                    with open(daily_csv, 'a', newline='', encoding='utf-8') as mf:
                        mw = csv.DictWriter(mf, fieldnames=['url','date','title','speaker','text'])
                        if write_header:
                            mw.writeheader()
                        mw.writerows(speeches)

        # sequential processing (no parallel)
        for pkg in pkg_ids:
            work_pkg(pkg)

    comp_file = os.path.join(output_dir, 'completed_days.txt')
    with open(comp_file, 'a', encoding='utf-8') as cf:
        cf.write(day_str + "\n")
    logging.info(f"=== Finished scrape for {day_str} ===\n")

# ------------------- Main -------------------

def main(output_dir: str, years: int, workers: int):
    global SUMMARY_CSV, BASE_QUERY

    OUTPUT_DIR  = output_dir
    SCRAPED_DIR = os.path.join(OUTPUT_DIR, 'scraped_output')
    SUMMARY_CSV = os.path.join(OUTPUT_DIR, 'summary.csv')
    BASE_QUERY  = "collection:CREC AND docClass:CREC AND (section:House OR section:Senate)"

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SCRAPED_DIR, exist_ok=True)

    with open(SUMMARY_CSV, 'w', newline='', encoding='utf-8') as sf:
        writer = csv.DictWriter(sf, fieldnames=['date','title','has_speech'])
        writer.writeheader()

    open(os.path.join(OUTPUT_DIR, 'completed_days.txt'), 'w').close()

    end   = date.today() - timedelta(days=1)
    start = date(end.year - years, end.month, end.day)
    days  = []
    cur   = end
    while cur >= start:
        days.append(cur)
        cur -= timedelta(days=1)

    logging.info(f"Will process {len(days)} days, sequentially.")
    for d in days:
        scrape_day(d.year, d.month, d.day, workers, OUTPUT_DIR)

if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description="Day-by-day CREC scraper w/ raw dumps (single key)"
    )
    p.add_argument('output_folder', help="Where to write output")
    p.add_argument('--years',     type=int, default=2, help="How many years back to go")
    p.add_argument('--workers',   type=int, default=1, help="(Unused) threads per day")
    args = p.parse_args()

    try:
        main(args.output_folder, args.years, args.workers)
    except KeyboardInterrupt:
        logging.info("Interrupted by user—exiting.")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")
        sys.exit(1)
