#!/bin/bash
#SBATCH -J congressional_scraper
#SBATCH -o congressional_scraper.out
#SBATCH -p standard-mem-m,standard-mem-l,medium-mem-2,medium-mem-1-m,high-mem-1,high-mem-2
#SBATCH --mem=8G
#SBATCH --exclusive

module purge
module load python/3

hostname
python congressional_scraper.py the congress_keyword_the_115.psv -r 200000 --start-congress 112 --end-congress 117
