import argparse
import os
import sys
import time
import csv
import logging
import threading
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any, Set
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import speaker_scraper

# ------------------- Configuration -------------------
BASE_API_URL        = 'https://api.govinfo.gov'
PAGE_SIZE           = 1000
RETRY_DELAY         = 15    # seconds on 429
MAX_RETRIES         = 3

# specify an API key here
demo_key = 'YOUR_DEMO_KEY'

# these get initialized once we see the first rate-limit header:
RATE_LIMIT_PER_HOUR: Optional[int] = None
RATE_INTERVAL:    Optional[float] = None   # seconds between calls

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
parsed_lock    = threading.Lock()

# single-key helper
def get_api_key() -> str:
    return demo_key

# ------------------- Rate-Limit Helpers -------------------
def rate_limit():
    """Sleep as needed to enforce the aggregate calls/hour limit."""
    global last_call_time, RATE_INTERVAL
    if RATE_INTERVAL is None:
        return
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
                    logging.info(f"Aggregate limit {RATE_LIMIT_PER_HOUR}/hr → interval {RATE_INTERVAL:.3f}s")
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


def get_mods(pkg: str, gran: str) -> str:
    """
    Returns the raw MODS XML string for the given granule.
    """
    url    = f"{BASE_API_URL}/packages/{pkg}/granules/{gran}/mods"
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
    pres = soup.find_all('pre')
    if not pres:
        return None
    texts = [p.get_text() for p in pres if p.get_text().strip()]
    return "\n\n".join(texts) if texts else None


def process_speeches(html: str) -> List[Dict[str, Any]]:
    txt = extract_pre_text(html)
    if not txt:
        return []
    parts = speaker_scraper.scrape(txt)
    out = []
    for speaker, body in parts:
        clean = body.replace('\n',' ').replace('\t',' ').strip()
        out.append({'speaker': speaker, 'text': clean})
    return out

# ------------------- MODS Parsing -------------------
def parse_congmember_metadata(mods_xml: str) -> List[Dict[str, str]]:
    """
    Parse the MODS XML to extract all <congMember role="SPEAKING"> elements.
    Returns a list of dicts with parsed_name, bioGuideId, full_name, party, state, chamber.
    """
    meta_list: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(mods_xml)
    except ET.ParseError:
        return meta_list

    ns = {'m': 'http://www.loc.gov/mods/v3'}
    for cm in root.findall('.//m:congMember', ns):
        if cm.get('role','').upper() != 'SPEAKING':
            continue

        parsed_elem = cm.find('m:name[@type="parsed"]', ns)
        if parsed_elem is None or not parsed_elem.text:
            continue
        parsed_name = parsed_elem.text.strip()

        fnf_elem = cm.find('m:name[@type="authority-fnf"]', ns)
        full_name = fnf_elem.text.strip() if fnf_elem is not None and fnf_elem.text else ''

        meta_list.append({
            'parsed_name': parsed_name,
            'bioGuideId':  cm.get('bioGuideId','').strip(),
            'full_name':   full_name,
            'party':       cm.get('party','').strip(),
            'state':       cm.get('state','').strip(),
            'chamber':     cm.get('chamber','').strip()
        })

    return meta_list

# ------------------- Worker for one day -------------------
def scrape_day(year: int, month: int, day: int, workers: int, output_dir: str):
    d       = date(year, month, day)
    day_str = d.isoformat()
    logging.info(f"=== Starting scrape for {day_str} ===")

    raw_base    = os.path.join(output_dir, 'raw_output')
    parsed_base = os.path.join(output_dir, 'parsed_house-senate_output')
    os.makedirs(raw_base, exist_ok=True)
    os.makedirs(parsed_base, exist_ok=True)

    query = f"{BASE_QUERY} AND publishdate:range({day_str},{day_str})"
    offset = None
    pkg_ids: Set[str] = set()

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
        return

    def work_pkg(pkg: str):
        for gran in get_granules(pkg):
            gid = gran.get('granuleId')
            if not gid:
                continue

            section = 'house' if 'PgH' in gid else 'senate' if 'PgS' in gid else None
            if section is None:
                continue

            chamber_value = 'House' if section == 'house' else 'Senate'

            html = get_htm(pkg, gid)
            if not html:
                continue

            day_dir   = os.path.join(raw_base, day_str)
            class_dir = os.path.join(day_dir, section)
            os.makedirs(class_dir, exist_ok=True)
            raw_file  = os.path.join(class_dir, f"{gid}.html")
            with open(raw_file, 'w', encoding='utf-8') as rf:
                rf.write(html)

            mods_xml       = get_mods(pkg, gid)
            metadata_list  = parse_congmember_metadata(mods_xml)
            lookup = { m['parsed_name']: m for m in metadata_list }

            summary = get_granule_summary(pkg, gid)
            title   = summary.get('title','').replace('\n',' ').strip()
            dstr    = summary.get('dateIssued','').strip()
            try:
                rec_date = datetime.fromisoformat(dstr).date()
            except Exception:
                rec_date = None
            if rec_date != d:
                continue

            speeches = process_speeches(html)
            if not speeches:
                continue

            enriched_rows = []
            for sp in speeches:
                speaker_text = sp['speaker']
                meta = lookup.get(speaker_text, {})

                gender = ''
                if speaker_text.startswith(('Ms.', 'Mrs.')):
                    gender = 'F'
                elif speaker_text.startswith('Mr.'):
                    gender = 'M'

                enriched_rows.append({
                    'granule_id': gid,
                    'date':       dstr,
                    'chamber':    chamber_value,
                    'title':      title,
                    'speaker':    speaker_text,
                    'text':       sp['text'],
                    'bioGuideId': meta.get('bioGuideId',''),
                    'full_name':  meta.get('full_name',''),
                    'party':      meta.get('party',''),
                    'state':      meta.get('state',''),
                    'gender':     gender
                })

            parsed_csv = os.path.join(parsed_base, f"{day_str}.csv")
            with parsed_lock:
                write_header = not os.path.exists(parsed_csv)
                with open(parsed_csv, 'a', newline='', encoding='utf-8') as pf:
                    fieldnames = [
                        'granule_id','date','chamber','title','speaker','text',
                        'bioGuideId','full_name','party','state','gender'
                    ]
                    writer = csv.DictWriter(pf, fieldnames=fieldnames)
                    if write_header:
                        writer.writeheader()
                    writer.writerows(enriched_rows)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for pkg in pkg_ids:
            pool.submit(work_pkg, pkg)

    logging.info(f"=== Finished scrape for {day_str} ===\n")

# ------------------- Main -------------------
def main(output_dir: str,
         years: int,
         workers: int,
         year_start: Optional[int] = None):
    global BASE_QUERY
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'raw_output'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'parsed_house-senate_output'), exist_ok=True)

    BASE_QUERY = "collection:CREC AND docClass:CREC AND (section:House OR section:Senate)"

    end_base = date.today() - timedelta(days=1)
    end_date = date(year_start, end_base.month, end_base.day) if year_start else end_base
    start_date = end_date.replace(year=end_date.year - years)

    days = []
    cur  = end_date
    while cur >= start_date:
        days.append(cur)
        cur -= timedelta(days=1)

    logging.info(f"Will process {len(days)} days, {workers} workers/day.")
    for d in days:
        scrape_day(d.year, d.month, d.day, workers, output_dir)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description="CREC scraper with speaker-metadata cross-reference")
    p.add_argument('output_folder', help="Where to write output")
    p.add_argument('--years',     type=int, default=2, help="How many years back to go")
    p.add_argument('--year-start', type=int, help="Optional starting year (e.g. 1995) for the first scrape date")
    p.add_argument('--workers',   type=int, default=4, help="Threads per day")
    args = p.parse_args()

    try:
        main(args.output_folder, args.years, args.workers, args.year_start)
    except KeyboardInterrupt:
        logging.info("Interrupted by user—exiting.")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")
        sys.exit(1)
