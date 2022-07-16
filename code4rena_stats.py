import csv
import json
import logging
import os
import requests
import requests_cache
from datetime import datetime, date, timedelta
from git import Repo

def get_number_of_repos(org):
	global base, headers
	url = base + f"orgs/{org}"
	return requests.get(url, headers=headers).json()['public_repos']

def get_repos(org, page=1):
	global base, headers
	url = base + f"orgs/{org}/repos?type=all&&per_page=100&page={page}"
	return requests.get(url, headers=headers).json()

def repo_creation_to_date(s): # format : [Y]-[M]-[D]T[H]:[M]:[S]Z
	return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').date()

if __name__ == "__main__":
	file_handler = logging.FileHandler("code4rena.log", mode='w')
	
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.INFO)
	logging.basicConfig(
		handlers=[file_handler, console_handler], 
		level=logging.DEBUG, 
		format='%(module)s:T+%(relativeCreated)d\t%(levelname)s %(message)s'
	)

	logging.addLevelName(logging.DEBUG, '[DEBUG]')
	logging.addLevelName(logging.INFO, '[*]')
	logging.addLevelName(logging.WARNING, '[!]')
	logging.addLevelName(logging.ERROR, '[ERROR]')
	logging.addLevelName(logging.CRITICAL, '[CRITICAL]')

	requests_cache.install_cache('code4rena_cache', expire_after=timedelta(days=1)) # Update repo data every day (prevent reaching API rate limit)
	base = f"https://api.github.com/"
	headers = {'User-Agent': 'Bot'}
	org = "code-423n4"

	logging.info(f"Fetching all public repos from {org}...")
	repos = []
	nb_public_repos = get_number_of_repos(org)
	for i in range(nb_public_repos//100 + 1):
		repos += get_repos(org, i + 1)
		logging.debug(f"Got {len(repos)} repos, page {i+1}/{nb_public_repos//100 + 1}")
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

	logging.info(f"Parsing data to CSV file...")
	count_rows = 0
	auditor_fields = ['contest_id', 'contest_sponsor', 'date', 'handle', 'address', 'risk']
	with open('code4rena.csv', 'w', newline='') as csvfile:
		csv_writer = csv.DictWriter(csvfile, fieldnames=auditor_fields, extrasaction='ignore')
		csv_writer.writeheader()
		for repo in os.listdir(repos_data_folder):
			for json_filename in os.listdir(repos_data_folder + repo + '/data/'):
				with open(repos_data_folder + repo + '/data/' + json_filename, 'r') as json_file:
					try:
						json_data = json.loads(json_file.read())
						json_data['contest_id'] = json_data['contest']
						json_data['contest_sponsor'] = " ".join(repo.split('-')[2:-1])
						json_data['date'] = "/".join(repo.split('-')[:2])
						csv_writer.writerow(json_data)
						count_rows += 1
					except Exception as e:
						logging.error(f"Failed to parse '{json_filename}'' for repo '{repo}': {e}")
			logging.debug(f"Parsing finished for repo '{repo}'")
	logging.info(f"Finished parsing data: wrote {count_rows} rows to CSV file [success]")