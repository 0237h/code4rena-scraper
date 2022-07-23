import logging
import sys

from dotenv import load_dotenv
from scrapers.WebScraper import *
from scrapers.GithubScraper import *

load_dotenv()

def scrape_leaderboard(web_scraper, leaderboard_url, leaderboard_csv_file=None):
	logging.info(f"Starting Code4rena leaderboard data scraping at '{leaderboard_url}'...")
	df = web_scraper.scrape_leaderboard_table(leaderboard_url)
	
	if (leaderboard_csv_file):
		df.to_csv(leaderboard_csv_file, index=False)
	
	logging.info(f"Finished Code4rena leaderboard data scraping: got '{len(df.index)}' rows of data [success]")
	return df

def scrape_contests(web_scraper, contests_url, contests_csv_file=None):
	logging.info(f"Starting Code4rena contests data scraping at '{contests_url}'...")
	df = web_scraper.scrape_contests_data(contests_url)
	
	if (contests_csv_file):
		df.to_csv(contests_csv_file, index=False)
	
	logging.info(f"Finished Code4rena contests data scraping: wrote '{len(df.index)}' rows of data [success]")
	return df

def scrape_github(github_scraper):
	logging.info(f"Starting Github data scraping for '{github_scraper.org}'...")
	github_scraper.scrape_repos() # TODO : Make scraper return pandas DataFrame for consistency

if __name__ == "__main__":
	file_handler = logging.FileHandler("code4rena.log", mode='w', encoding='utf8')
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.INFO)
	logging.basicConfig(
		handlers=[file_handler, console_handler], 
		level=logging.DEBUG, 
		format='%(module)s:T+%(relativeCreated)d\t%(levelname)s %(message)s'
	)
	logging.getLogger('selenium').setLevel(logging.WARNING) # Prevent log file from being filed with Selenium debug output

	logging.addLevelName(logging.DEBUG, '[DEBUG]')
	logging.addLevelName(logging.INFO, '[*]')
	logging.addLevelName(logging.WARNING, '[!]')
	logging.addLevelName(logging.ERROR, '[ERROR]')
	logging.addLevelName(logging.CRITICAL, '[CRITICAL]')
	
	leaderboard_url = "https://code4rena.com/leaderboard"
	leaderboard_csv_file = 'leaderboard_code4rena.csv'

	contests_url = "https://code4rena.com/contests"
	contests_csv_file = 'contests_code4rena.csv'
	
	web_scraper = WebScraper(console_handler)
	github_scraper = GithubScraper(console_handler)
	target = sys.argv[1].lower() # TODO : Parse command line arguments

	if (target == 'leaderboard'):
		scrape_leaderboard(web_scraper, leaderboard_url, leaderboard_csv_file)
	elif (target == 'contests'):
		scrape_contests(web_scraper, contests_url, contests_csv_file)
	elif (target == 'github'):
		scrape_github(github_scraper)
	else:
		scrape_leaderboard(web_scraper, leaderboard_url, leaderboard_csv_file)
		scrape_contests(web_scraper, contests_url, contests_csv_file)
		scrape_github(github_scraper)
