# Congressional Data Scraper

When provided with a search term, the Congressional Data Scraper (CDS) will scrape the plain text version of the Daily Editions of the U.S. Congressional Records from "congress.gov" whose titles contain your search term. The output is a .csv file with columns for:
 
- Record Name
- Page Range
- Date
- Speaker Name
- Speech Text
- Search Term
- URL

### Usage


Takes 
Search term (can be one or more words) 
Start Year
End Year




```


```


## Appendix

### About the Data
The Congressional Record is the official record of the proceedings and debates of the United States Congress (from 1873 to the present moment). It is published online daily when Congress is in session. 

It can be confusing how many different versions of data are produced by Congress. This section gives a high level overview of the data collected by CDS. 

CDS collects the plain text versions of the Daily Edition of the U.S. Congressional Records from "congress.gov." It can collected data from the day it is run through the year 1995. CDS does not collect the Bound Edition, which is a PDF version of the record. Subsequently, it does not collect data from before the year 1995 because this data is served exclusively in PDF form, as opposed to the Daily Edition which is served in plain text embedded into the HTML of a record’s web page as well as in PDF form. 

There are a few minor differences between the Daily Edition and the Bound edition. These differences have to do with pagination, name prefixing, and other conventions of the like. For a full description of the differences between the two versions, see [Gov Info](https://www.govinfo.gov/help/crecb).  



Notes: to get title, scrape h2 (heading 2)
