import logging
import sys

from dotenv import load_dotenv
from scrapers.WebScraper import *
from scrapers.GithubScraper import *

load_dotenv()

def scrape(scrape_method, scrape_data_desc, url, csv_file=None):
	logging.info(f"Starting {scrape_data_desc} data scraping at '{url}'...")
	df = scrape_method(url)
	
	if (csv_file):
		df.to_csv(csv_file, index=False)
	
	logging.info(f"Finished {scrape_data_desc} data scraping: got {len(df.index)} rows of data [success]")
	return df	

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

	github_org = "code-423n4"
	github_csv_file = 'github_code4rena.csv'
	
	github_scraper = GithubScraper(console_handler)
	target = sys.argv[1].lower() # TODO : Parse command line arguments

	if (target == 'github'):
		scrape(github_scraper.scrape_repos, "Github repos", github_org, github_csv_file)
	else:
		web_scraper = WebScraper(console_handler) # Initialize Selenium driver only if needed
		if (target == 'leaderboard'):
			scrape(web_scraper.scrape_leaderboard_table, "Code4rena leaderboard", leaderboard_url, leaderboard_csv_file)
		elif (target == 'contests'):
			scrape(web_scraper.scrape_contests_data, "Code4rena contests", contests_url, contests_csv_file)
		else:
			scrape(web_scraper.scrape_leaderboard_table, "Code4rena leaderboard", leaderboard_url, leaderboard_csv_file)
			scrape(web_scraper.scrape_contests_data, "Code4rena contests", contests_url, contests_csv_file)
			scrape(github_scraper.scrape_repos, "Github repos", github_org, github_csv_file)
