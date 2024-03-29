Note: We want everyone to have the ability to collect Congressional Records! If you have never used Python before watch this [3 minute video]() and by the end you will be collecting data on a spreadsheet. 

# Congressional Data Scraper
The Congressional Data Scraper (CDS) scrapes the plain text version of the Daily Editions of the U.S. Congressional Records from "congress.gov" that contain a search term. It outputs a .csv file with columns for:
 
- URL
- Date
- Title (of Record)
- Speaker
- Text

CDS will export records from a results page before transitioning to the next page. By default, CDS starts at the 104th Congress (which is the first Congress where records were consistently digitized in HTML).

## Usage

Required Parameters: 
- `search_term` return records with this term
- `output_file` name of export file

Optional Parameters:
- `-r, --result_count` number of records to query (default 9,000 records)
- `--start-congress` specify first congress to query (default 104th Congrss, inclusive)
- `--end-congress` specify last congress to query (default latest congress)
- `--default-retry-delay` length of time to wait when retry time is not offered (in seconds) 
- `--sort` options to sort results
- `--proxy` send trafficking through one or more proxy separated by a space
- `-h` see help pages in terminal 

### Examples

Scrape and export Congressional Records containing the word "climate." By default, this will start at the 104th Congress and query 9,000 files. 

```
python congressional_scraper.py climate congress_records_with_climate.csv
```

Scrape and export 1,000 Congressional Records containing the word "climate" starting with the 104th Congress.  

```
python congressional_scraper.py climate congress_records_with_climate.csv -r 1000
```

Scrape and export 200,000 Congressional Records containing the word "climate" starting with the 114th Congress and ending with the 117th Congress. 

```
python congressional_scraper.py the congress_keyword_the.psv -r 200000 --start-congress 114 --end-congress 117
```

Route trafficking via two proxy addresses.

```
python congressional_scraper.py climate congress_records_with_climate.csv --proxy http://1.1.1.1 https://1.1.1.1
```

## For More Information ...
... see our wiki: 
- [About the Data](https://github.com/stephbuon/congressional-data-scraper/wiki/About-the-Data)
- [Number of Records Per Caucus](https://github.com/stephbuon/congressional-data-scraper/wiki/Number-of-Records-Per-Caucus)
- [Time Requirements for Scraping Bulk Data/Retry Times](https://github.com/stephbuon/congressional-data-scraper/wiki/Retry-Times)
