#!/bin/bash
#SBATCH -J congressional_scraper
#SBATCH -o congressional_scraper.out
#SBATCH -p standard-mem-m,standard-mem-l,medium-mem-2,medium-mem-1-m,high-mem-1,high-mem-2
#SBATCH --mem=8G
#SBATCH --exclusive

module purge
module load python/3

hostname
python congressional_scraper.py the congress_keyword_the.psv -r 720000 --start-congress 104 --end-congress 117 --default-retry-delay 1800  --proxy http://10.210.15.2:3128/ https://10.210.15.2:3128/
