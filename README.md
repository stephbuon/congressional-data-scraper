# Congressional Data Scraper
The Congressional Data Scraper (CDS) scrapes the plain text version of the Daily Editions of the U.S. Congressional Records from "congress.gov" that contain a search term. It outputs a .csv file with columns for:
 
- URL
- Date
- Title (of Record)
- Speaker
- Text

CDS will export records from a results page before transitioning to the next page. By default, CDS starts at the 105th Congress (which is the first Congress where Records were consistently digitized). 

## Usage

Required Parameters: 
- `search_term` return records with this term
- `output_file` name of export file

Optional Parameters:
- `-r, --result_count` number of records to query (default 9,000 records)
- `--start-congress` specify first congress to query (default 105th Congrss)
- `--end-congress` specify last congress to query (default latest congress)
- `--default-retry-delay` ASK
- `--sort` ASK

### Useage Examples:

Scrape and export Congressional Records containing the word "climate." By default, this will start at the 105th Congress and query 9,000 files. 

```
python3 congressional_scraper.py climate congress_records_with_climate.csv
```

Scrape and export 1,000 Congressional Records containing the word "climate" starting at the 105th Congress.  

```
python3 congressional_scraper.py climate congress_records_with_climate.csv -r 1000
```

Scrape and export 200,000 Congressional Records containing the word "climate" starting at the 114th Congress and ending at the 117th Congress. 

```
python congressional_scraper.py the congress_keyword_the.psv -r 200000 --start-congress 114 --end-congress 117
```

## Appendix

### About the Data
The Congressional Record is the official record of the proceedings and debates of the United States Congress (from 1873 to the present moment). It is published online daily when Congress is in session. 

It can be confusing how many different versions of data are produced by Congress. This section gives a high level overview of the data collected by CDS. 

CDS collects the plain text versions of the Daily Edition of the U.S. Congressional Records from "congress.gov." It can collected data from the day it is run through the year 1995. CDS does not collect the Bound Edition, which is a PDF version of the record. Subsequently, it does not collect data from before the year 1995 because this data is served exclusively in PDF form, as opposed to the Daily Edition which is served in plain text embedded into the HTML of a record’s web page as well as in PDF form. 

There are a few minor differences between the Daily Edition and the Bound edition. These differences have to do with pagination, name prefixing, and other conventions of the like. For a full description of the differences between the two versions, see [Gov Info](https://www.govinfo.gov/help/crecb).  

### Scraping Bulk Data
The "congress.gov" website mandates retry times after an amount of API hits. The website does not specify or request lengths for retry times, however. Therefore, when possible, we catch the retry time, usually ~8 minutes. Otherwise, we impose our own retry time of 10 minutes. 

This can make time estimation hard. For more information, see our CDS [Wiki](). 
