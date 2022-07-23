import csv
import json
import logging
import os
import requests
import requests_cache
import time

from datetime import datetime, date, timedelta
from git import Repo

class GithubScraper():
	"""docstring for GithubScraper"""
	def __init__(self, console_handler):
		super(GithubScraper, self).__init__()
		requests_cache.install_cache('code4rena_cache', expire_after=timedelta(days=1)) # Cache repo data for one day (prevent reaching API rate limit)
		self.console_handler = console_handler
		self.org = "code-423n4"
		self.base = f"https://api.github.com/"
		self.headers = {'Authorization': 'token ' + os.getenv('API_ACCESS_TOKEN'), 'User-Agent': 'Bot'} # Using auth bumps the rate limit to 5_000 requests per HOUR 

	def _check_request(self, req):
		if (req.status_code == 403 or req.status_code == 404):
			logging.critical(f"Request returned {req.status_code}: {req.json()}")
			exit(1)
		elif all(k in req.headers for k in ['x-ratelimit-limit', 'x-ratelimit-remaining']):
			logging.debug(f"Rate limit: {req.headers['x-ratelimit-remaining']} requests remaining (limit: {req.headers['x-ratelimit-limit']})")

		return req

	def _get_paginated(self, start_url, redirect=None):
		url = redirect if redirect != None else (self.base + start_url)
		return self._check_request(requests.get(url, headers=self.headers))

	def get_repos(self, redirect=None):
		return self._get_paginated(f"orgs/{self.org}/repos?type=all&per_page=100", redirect)

	def get_issues(self, repo, redirect=None):
		return self._get_paginated(f"repos/{self.org}/{repo}/issues?state=all&per_page=100", redirect)

	def get_next_page_url(self, link_header): # Link header format: <url>; rel=[prev|next|last], ...
		if (link_header == None):
			return None

		try:
			for (url, rel) in [x.split(';') for x in link_header.split(',')]:
				if (rel.strip().split('=')[1].strip('\"') == "next"): # Split 'rel=[prev|next|last]'
					return url.strip().replace('<', '').replace('>', '')
		except ValueError as e:
			pass

		return None

	def is_last_page(self, headers):
		return 'Link' not in headers or 'next' not in headers['Link']

	def repo_creation_to_date(self, s): # format : [Y]-[M]-[D]T[H]:[M]:[S]Z
		return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').date()

	def scrape_repos(self):
		logging.info(f"Fetching all public repos from {self.org}...")
		repos = []
		req = requests.Response()
		req.headers = {'Link': 'next'} # Run loop at least once
		while not(self.is_last_page(req.headers)):
			next_page_url = self.get_next_page_url(req.headers['Link'])
			req = self.get_repos(next_page_url)
			repos += req.json()
			logging.debug(f"Got {len(repos)} repos, page {'1' if next_page_url == None else next_page_url[next_page_url.rindex('=')+1:]}")
		logging.info(f"Fetched {len(repos)} repos from {self.org} [success]")

		# Keep only audits reports starting from 20 March 2021 (earlier repos used a different format for tracking contributions)
		repos = list(filter(lambda repo: "findings" in repo['name'] and self.repo_creation_to_date(repo['created_at']) > date(2021, 3, 20), repos))
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
		self.console_handler.terminator = "\r"
		for repo in repos:
			req = requests.Response()
			req.headers = {'Link': 'next'} # Run loop at least once
			count_repo_issues = 0
			while not(self.is_last_page(req.headers)):
				next_page_url = self.get_next_page_url(req.headers['Link'])
				req = self.get_issues(repo['name'], next_page_url)
				issues[repo['name']] += req.json()
				count_repo_issues += len(issues[repo['name']])
				logging.debug(f"Got {count_repo_issues} issues for repo '{repo['name']}', page {'1' if next_page_url == None else next_page_url[next_page_url.rindex('=')+1:]}")
			logging.info(f"Processed {repos.index(repo) + 1} / {len(repos)} repos")
		self.console_handler.terminator = "\n"
		logging.info(f"Got {sum([len(k) for k in issues.values()])} total issues in {len(repos)} repos from {self.org} [success]")

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
		self.console_handler.terminator = "\r"
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
		self.console_handler.terminator = "\n"
		logging.info(f"Finished Github data scraping: wrote {count_rows} rows to '{github_csv_file}' [success]")
