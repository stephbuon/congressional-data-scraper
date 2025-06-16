Note: We want everyone to have the ability to collect Congressional Records! If you have never used Python before watch this [3 minute video]() and by the end you will be collecting data on a spreadsheet. 

# Congressional Data Scraper
The Congressional Data Scraper (CDS) scrapes the HTML version of the Daily Editions of the U.S. Congressional Records from "congress.gov" for the House and Senate from the present to a specified number of years back. Note that as the goal is to capture spoken text, it does not save the Daily Digest or Extensions of Remarks files. It outputs files in two folders: 

raw_output: Contains a folder for each day. Within each day, contains a 'house' and 'senate' folder. Within each of these folders, contains HTML files for each granule associated with that day.

parsed_house-senate_output: Contains a .csv for each day with the following columns, parsed with the speaker_scraper:
 
- granule_id
- date
- chamber (house or senate) 
- title (title of speech/section)
- speaker
- text (content of speech
- bioGuideId (see bioguide.congress.gov)
- full_name (speaker first name, middle initial, last name)
- party (D, R, and possibly I)
- state
- gender (for speakers with title "Mr.," "Ms.," or "Mrs.")

## Usage

Required Parameters: 
- `output_folder` name of folder to store output

Optional Parameters:
- `--years` number of years to go back (default 2, starting from today or year specified in year-start) 
- `--year-start` year to start at (scrapes backwards from there) 

### Examples

Scrape all Congressional Records going back from today

```
python congressional_scraper.py "output_dir" --years 35      #set years >30 to scrape all records (daily edition starts 1995)
```

## For More Information ...
... see our wiki: 
- [About the Data](https://github.com/stephbuon/congressional-data-scraper/wiki/About-the-Data)
- [Number of Records Per Caucus](https://github.com/stephbuon/congressional-data-scraper/wiki/Number-of-Records-Per-Caucus)
- [Time Requirements for Scraping Bulk Data/Retry Times](https://github.com/stephbuon/congressional-data-scraper/wiki/Retry-Times)
