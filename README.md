# Congressional Data Scraper
The Congressional Data Scraper (CDS) scrapes the plain text version of the Daily Editions of the U.S. Congressional Records from "congress.gov" that contain your search term. It outputs a .csv file with columns for:
 
- URL
- Title (of Record)
- Speaker Name
- Text
- Date 

## Usage

Required Parameters: 
- `search_term` : return records with this term
- `output_file` : name of export file. Will write to file at the end of each page

Optional Parameters:
- `-r` : number of results

For example: 

```
python3 congressional_scraper.py climate congress_records_with_climate.csv

python3 congressional_scraper.py climate congress_records_with_climate.csv -r 1000

```

## Appendix

### About the Data
The Congressional Record is the official record of the proceedings and debates of the United States Congress (from 1873 to the present moment). It is published online daily when Congress is in session. 

It can be confusing how many different versions of data are produced by Congress. This section gives a high level overview of the data collected by CDS. 

CDS collects the plain text versions of the Daily Edition of the U.S. Congressional Records from "congress.gov." It can collected data from the day it is run through the year 1995. CDS does not collect the Bound Edition, which is a PDF version of the record. Subsequently, it does not collect data from before the year 1995 because this data is served exclusively in PDF form, as opposed to the Daily Edition which is served in plain text embedded into the HTML of a record’s web page as well as in PDF form. 

There are a few minor differences between the Daily Edition and the Bound edition. These differences have to do with pagination, name prefixing, and other conventions of the like. For a full description of the differences between the two versions, see [Gov Info](https://www.govinfo.gov/help/crecb).  



Notes: to get title, scrape h2 (heading 2)
