import csv
import json
import logging
import os
import pandas as pd
import requests
import requests_cache
import time

from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from git import Repo
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

load_dotenv()

def _check_request(req):
	if (req.status_code == 403 or req.status_code == 404):
		logging.critical(f"Request returned {req.status_code}: {req.json()}")
		exit(1)
	elif all(k in req.headers for k in ['x-ratelimit-limit', 'x-ratelimit-remaining']):
		logging.debug(f"Rate limit: {req.headers['x-ratelimit-remaining']} requests remaining (limit: {req.headers['x-ratelimit-limit']})")

	return req

def _get_paginated(org, start_url, redirect=None):
	global base, headers
	url = redirect if redirect != None else (base + start_url)
	return _check_request(requests.get(url, headers=headers))

def get_repos(org, redirect=None):
	return _get_paginated(org, f"orgs/{org}/repos?type=all&per_page=100", redirect)

def get_issues(org, repo, redirect=None):
	return _get_paginated(org, f"repos/{org}/{repo}/issues?state=all&per_page=100", redirect)

def get_next_page_url(link_header): # Link header format: <url>; rel=[prev|next|last], ...
	if (link_header == None):
		return None

	try:
		for (url, rel) in [x.split(';') for x in link_header.split(',')]:
			if (rel.strip().split('=')[1].strip('\"') == "next"): # Split 'rel=[prev|next|last]'
				return url.strip().replace('<', '').replace('>', '')
	except ValueError as e:
		pass

	return None

def is_last_page(headers):
	return 'Link' not in headers or 'next' not in headers['Link']

def repo_creation_to_date(s): # format : [Y]-[M]-[D]T[H]:[M]:[S]Z
	return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').date()

def scrape_leaderboard_table(url):
	logging.debug("Starting Selenium driver...")
	browser_options = Options()
	browser_options.headless = True
	driver = webdriver.Firefox(options=browser_options, executable_path=os.getenv('FIREFOX_DRIVER_PATH'))
	logging.debug(f"Selenium driver started [success]")

	logging.info(f"Parsing dropdown options from '{url}'...")
	driver.get(url)
	periods = driver.find_element(By.XPATH, "//select[@class='dropdown']").find_elements(By.TAG_NAME, 'option')
	logging.info(f"Got {len(periods)} options from '{url}' [success]")

	leaderboard_columns = ['period', 'handle', 'prize_money', 'total_reports', 'high_all', 'high_solo', 'med_all', 'med_solo', 'gas_all']
	leaderboard_data = pd.DataFrame(columns=leaderboard_columns)
	
	logging.info(f"Parsing leaderboard data for each option...")
	console_handler.terminator = "\r"
	for period in periods:
		period.click()
		soup = BeautifulSoup(driver.page_source, features="lxml")
		table = soup.find('table', {'class': 'leaderboard-table'})
		
		df = pd.read_html(str(table))[0]
		df.columns = leaderboard_columns
		df["period"] = period.text
		df["prize_money"] = df["prize_money"].str.replace(r'\$|,', '', regex=True).astype(float)

		leaderboard_data = pd.concat([leaderboard_data, df])
		logging.info(f"Parsed {periods.index(period) + 1}/{len(periods)} options ({len(df.index)} rows added for '{period.text}')")
	console_handler.terminator = "\n"

	driver.quit()
	return leaderboard_data.reset_index(drop=True)

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

	requests_cache.install_cache('code4rena_cache', expire_after=timedelta(days=1)) # Cache repo data for one day (prevent reaching API rate limit)
	base = f"https://api.github.com/"
	headers = {'Authorization': 'token ' + os.getenv('API_ACCESS_TOKEN'), 'User-Agent': 'Bot'} # Using auth bumps the rate limit to 5_000 requests per HOUR 
	org = "code-423n4"
	leaderboard_url = "https://code4rena.com/leaderboard"

	logging.info(f"Starting code4rena leaderboard data scraping at '{leaderboard_url}'...")
	df = scrape_leaderboard_table(leaderboard_url)
	leaderboard_csv_file = 'leaderboard_code4rena.csv'
	df.to_csv(leaderboard_csv_file, index=False)
	logging.info(f"Finished code4rena leaderboard data scraping: wrote '{len(df.index)}' rows to '{leaderboard_csv_file}' [success]")
	
	logging.info(f"Starting Github data scraping for '{org}'...")
	logging.info(f"Fetching all public repos from {org}...")
	repos = []
	req = requests.Response()
	req.headers = {'Link': 'next'} # Run loop at least once
	while not(is_last_page(req.headers)):
		next_page_url = get_next_page_url(req.headers['Link'])
		req = get_repos(org, next_page_url)
		repos += req.json()
		logging.debug(f"Got {len(repos)} repos, page {'1' if next_page_url == None else next_page_url[next_page_url.rindex('=')+1:]}")
	logging.info(f"Fetched {len(repos)} repos from {org} [success]")

	# Keep only audits reports starting from 20 March 2021 (earlier repos used a different format for tracking contributions)
	repos = list(filter(lambda repo: "findings" in repo['name'] and repo_creation_to_date(repo['created_at']) > date(2021, 3, 20), repos))
	if (len(repos) == 0):
		logging.critical(f"No completed audits repos found, terminating...")
		exit(1)

	total_repos_size = sum([repo['size'] for repo in repos])
	logging.info(f"Found {len(repos)} completed audits repos (total size: {total_repos_size} Kb)")
	
	repos_data_folder = "repos_data/"
	os.makedirs(repos_data_folder, exist_ok=True) # Create cloning directory if needed
	cloned_repos = 0
	logging.info(f"Cloning new repositories to '{repos_data_folder}'...")
	for repo in repos:
		if not(os.path.isdir(repos_data_folder + repo['name'])):
			logging.info(f"Cloning {repo['name']} ({repos.index(repo) + 1}/{len(repos)})...")
			Repo.clone_from(repo['clone_url'], repos_data_folder + repo['name'])
			cloned_repos += 1

	if (cloned_repos > 0):
		logging.info(f"Cloned {cloned_repos} new repos to '{repos_data_folder}' [success]")
	else:
		logging.warning(f"No new repos to clone")

	logging.info("Getting issues data for each repo (this may take some time)...")
	issues = {repo['name'] : [] for repo in repos}
	console_handler.terminator = "\r"
	for repo in repos:
		req = requests.Response()
		req.headers = {'Link': 'next'} # Run loop at least once
		count_repo_issues = 0
		while not(is_last_page(req.headers)):
			next_page_url = get_next_page_url(req.headers['Link'])
			req = get_issues(org, repo['name'], next_page_url)
			issues[repo['name']] += req.json()
			count_repo_issues += len(issues[repo['name']])
			logging.debug(f"Got {count_repo_issues} issues for repo '{repo['name']}', page {'1' if next_page_url == None else next_page_url[next_page_url.rindex('=')+1:]}")
		logging.info(f"Processed {repos.index(repo) + 1} / {len(repos)} repos")
	console_handler.terminator = "\n"
	logging.info(f"Got {sum([len(k) for k in issues.values()])} total issues in {len(repos)} repos from {org} [success]")

	'''
	At this point we have for each public contest report:
		- Sponsor
		- Rough date for when it took place (month, year)
		- Participants
			- Handle
			- Address
			- Issues reported
		- Issues (= audit submission) tags
			- Risk (QA, Non-critical/0, Low/1, Med/2, High/3)
			- Sponsor acknowledged, confirmed, disputed, addressed/resolved
			- Duplicate
			- Is gas optimization
			- Is judged invalid
			- Has been upgraded by judge
			- Has been withdrawn by warden
			... others
	'''

	logging.info(f"Writing data to CSV file (this may take some time)...")
	github_csv_file = 'github_code4rena.csv'
	csv_headers = ['contest_id', 'handle', 'address', 'risk', 'title', 'issueId', 'issueUrl', 'contest_sponsor', 'date', 'tags']
	count_rows = 0
	console_handler.terminator = "\r"
	with open(github_csv_file, 'w', newline='') as csvfile:
		csv_writer = csv.writer(csvfile)
		csv_writer.writerow(csv_headers) # CSV Headers
		repo_names = os.listdir(repos_data_folder)
		for repo in repo_names:
			repo_issues = issues[repo]
			for json_filename in os.listdir(repos_data_folder + repo + '/data/'):
				with open(repos_data_folder + repo + '/data/' + json_filename, 'r') as json_file:
					'''
					Sample JSON data file:
						{
						  "contest": "[ID]",
						  "handle": "[HANDLE]",
						  "address": "[ADDRESS]",
						  "risk": "[1/2/3]",
						  "title": "[TITLE]",
						  "issueId": [ISSUE NUMBER],
						  "issueUrl": "[UNUSED]"
						}
					'''
					try:
						json_data = json.loads(json_file.read()) # Loads dict from json data file
						issue = next(i for i in repo_issues if i['number'] == json_data['issueId']) # Get issue details

						# Additional infos
						json_data['contest_sponsor'] = " ".join(repo.split('-')[2:-1])
						json_data['date'] = "/".join(repo.split('-')[:2])
						json_data['tags'] = ";".join([l['name'] for l in issue['labels']])
						
						if (len(json_data.values()) == len(csv_headers)): # TODO: Include default values for malformed data
							csv_writer.writerow(json_data.values())
						count_rows += 1
					except Exception as e:
						logging.warning(f"Failed to parse '{json_filename}'' for repo '{repo}': {e}")
			logging.info(f"Processed {repo_names.index(repo) + 1} / {len(repo_names)} repos")
	console_handler.terminator = "\n"
	logging.info(f"Finished Github data scraping: wrote {count_rows} rows to '{github_csv_file}' [success]")