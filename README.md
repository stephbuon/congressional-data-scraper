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
- `--default-retry-delay` ASK
- `--sort` ASK

### Useage Examples:

Scrape and export Congressional Records containing the word "climate." By default, this will start at the 104th Congress and query 9,000 files. 

```
python3 congressional_scraper.py climate congress_records_with_climate.csv
```

Scrape and export 1,000 Congressional Records containing the word "climate" starting with the 104th Congress.  

```
python3 congressional_scraper.py climate congress_records_with_climate.csv -r 1000
```

Scrape and export 200,000 Congressional Records containing the word "climate" starting with the 114th Congress and ending with the 117th Congress. 

```
python congressional_scraper.py the congress_keyword_the.psv -r 200000 --start-congress 114 --end-congress 117
```

## Appendix

### About the Data
The Congressional Record is the official record of the proceedings and debates of the United States Congress (from 1873 to the present moment). It is published online daily when Congress is in session. 

It can be confusing how many different versions of data are produced by Congress. This section gives a high level overview of the data collected by CDS. 

CDS collects the plain text versions of the Daily Edition of the U.S. Congressional Records from "congress.gov." It can collected data from the day it is run through the year 1995. CDS does not collect the Bound Edition, which is a PDF version of the record. Subsequently, it does not collect data from before the year 1995 because this data is served exclusively in PDF form, as opposed to the Daily Edition which is served in plain text embedded into the HTML of a record’s web page as well as in PDF form. 

There are a few minor differences between the Daily Edition and the Bound edition. These differences have to do with pagination, name prefixing, and other conventions of the like. For a full description of the differences between the two versions, see [Gov Info](https://www.govinfo.gov/help/crecb).  

### Scraping Bulk Data: Time Requirements
The "congress.gov" website mandates retry times after an amount of API hits. However, the website does not specify or request lengths for retry times or the number of queries that can be made before a retry time is imposed. Therefore, when possible, we catch the retry time, usually ~8 minutes. Otherwise, we impose our own retry time of 10 minutes. 

The length of the retry times can make scraping the data a slow process and can also make estimating time to completion difficult. To read about our experiences/accounts on how we deal with this problem, see our CDS [wiki](https://github.com/stephbuon/congressional-data-scraper/wiki/Retry-Times). 

### Number of Records 
The 104th Congress onward digitize around 50,000 records each. View the "congress.gov" [search page](https://www.congress.gov/search?q={%22congress%22%3A[%22117%22]%2C%22search%22%3A%22the%22%2C%22source%22%3A%22congrecord%22}) for specifics on how many records make up a specific congressional caucus. For step-by-step instructions on how to use "congress.gov" to find this information, see the CDS [wiki](https://github.com/stephbuon/congressional-data-scraper/wiki/Congressional-Caucus-Record-Numbers)
