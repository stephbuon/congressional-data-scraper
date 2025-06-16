#!/bin/bash
#SBATCH --job-name=crecScraper
#SBATCH --mem=6G

python congressional_scraper.py "output_dir" --years 35
