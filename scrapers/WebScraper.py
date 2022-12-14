import logging
import os
import pandas as pd
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException

class WebScraper():
	"""docstring for WebScraper"""
	def __init__(self, console_handler):
		super(WebScraper, self).__init__()
		self.console_handler = console_handler
		logging.info("Starting Selenium driver (firefox headless)...")
		browser_options = Options()
		browser_options.headless = True
		self.driver = webdriver.Firefox(options=browser_options, executable_path=GeckoDriverManager().install())
		logging.info(f"Selenium driver started [success]")

	def __del__(self):
		self.driver.quit()

	def scrape_leaderboard_table(self, url):
		logging.info(f"Parsing dropdown options from '{url}'...")
		self.driver.get(url)
		time.sleep(1) # Wait for JS to load page

		periods = self.driver.find_element(By.XPATH, "//select[@class='dropdown']").find_elements(By.TAG_NAME, 'option')
		logging.info(f"Got {len(periods)} options from '{url}' [success]")

		leaderboard_columns = ['period', 'handle', 'prize_money', 'total_reports', 'high_all', 'high_solo', 'med_all', 'med_solo', 'gas_all']
		leaderboard_data = pd.DataFrame(columns=leaderboard_columns)
		
		logging.info(f"Parsing leaderboard data for each option...")
		self.console_handler.terminator = "\r"
		for period in periods:
			period.click()
			time.sleep(1) # Wait for JS to load page

			table = BeautifulSoup(self.driver.find_element(By.XPATH, "//table[@class='leaderboard-table']").get_attribute("outerHTML"), 'lxml')
			for div in table.find_all(attrs={'class': 'sb-avatar__text'}): # Remove avatar text <span> for correct parsing of wardens handle
				div.extract()			

			df = pd.read_html(str(table))[0]
			df.columns = leaderboard_columns
			df["period"] = period.text
			df["prize_money"] = df["prize_money"].str.replace(r'\$|,', '', regex=True).astype(float)

			is_team_data = []
			for div in table.find_all(attrs={'class': 'wrapper-competitor'}):
				is_team_data.append(div.find('div', attrs={'class': 'wrapper-members'}) != None)
			df["is_team"] = is_team_data 
			
			leaderboard_data = pd.concat([leaderboard_data, df])
			logging.info(f"Parsed {periods.index(period) + 1}/{len(periods)} options ({len(df.index)} rows added for '{period.text}')")
		self.console_handler.terminator = "\n"

		leaderboard_data.insert(2, 'is_team', leaderboard_data.pop('is_team')) # Re-order column next to 'handle' column
		return leaderboard_data.reset_index(drop=True)

	def scrape_contests_data(self, url):
		logging.info(f"Getting all contests links from '{url}'...")
		self.driver.get(url)
		time.sleep(1) # Wait for JS to load page

		contests = []
		for c in self.driver.find_elements(By.XPATH, "//div[@class='wrapper-contest-content']"):
			try:
				contests.append(c.find_element(By.XPATH, "//div[contains(@class, 'contest-repo')]").get_attribute("href"))
			except NoSuchElementException as e:
				logging.warning(f"Could not find contest link for '{c.find_element(By.TAG_NAME, 'h4').get_attribute('innerText')}'\n")
				continue
		logging.info(f"Got {len(contests)} contests from '{url}' [success]")

		contest_table_columns = ['handle', 'prize_money', 'total_reports', 'high_all', 'high_solo', 'med_all', 'med_solo', 'gas_all']
		contests_columns = ['contest_report_repo', 'contest_sponsor', 'contest_desc', 'start', 'end', 'prize_pool'] + contest_table_columns
		contests_data = pd.DataFrame(columns=contests_columns)
		
		logging.info(f"Scraping each contest entry data...")
		self.console_handler.terminator = "\r"
		for contest_link in contests:
			logging.debug(f"Getting data for '{contest_link}'...")
			self.driver.get(contest_link)
			time.sleep(1) # Wait for JS to load page

			try:
				contest_tabs = self.driver.find_element(By.XPATH, "//div[@class='contest-tabs']")
			except NoSuchElementException as e:
				logging.warning(f"Could not parse '{contest_link}': contests tabs not found\n")
				continue

			try:
				leaderboard_table = contest_tabs.find_element(By.XPATH, "//table[@class='leaderboard-table']")
			except NoSuchElementException as e:
				logging.warning(f"No awards distributed yet for '{contest_link}'\n")
				continue			

			df = pd.read_html(leaderboard_table.get_attribute("outerHTML"))[0]
			df.columns = ["id"] + contest_table_columns
			df.drop("id", axis=1, inplace=True)

			df["contest_report_repo"] = ''
			repos_buttons = self.driver.find_element(By.XPATH, "//div[@class='button-wrapper']")
			if (len(repos_buttons.find_elements(By.TAG_NAME, 'a')) > 1): # Check that the contest report has been published 
				'''
					Report link is either a PDF file (older contests) or a link containing the repo name which can be used with the scraped Github data
					Examples : 
						https://ipfs.io/ipfs/bafybeicjla2h26q3wz4s344bsrtvhkxr3ypm44owvrzyorb2t6tcptlmem/C4%20Slingshot%20report.pdf
						https://code4rena.com/reports/2021-06-pooltogether
				'''
				report_link = repos_buttons.find_elements(By.TAG_NAME, 'a')[-1].get_attribute("href")
				df["contest_report_repo"] = '' if not 'code4rena.com/reports/' in report_link else report_link[report_link.rindex('/') + 1:]

			contest_header_div = self.driver.find_element(By.XPATH, "//div[@class='top-section-text']")
			df["contest_sponsor"] = contest_header_div.find_element(By.TAG_NAME, 'h1').get_attribute('innerText').lower().replace(' ', '').replace('contest', '')
			df["contest_desc"] = contest_header_div.find_element(By.TAG_NAME, 'p').get_attribute('innerText')
			
			contest_date_div = self.driver.find_element(By.XPATH, "//div[@class='contest-tippy-top']")
			dates = contest_date_div.find_element(By.TAG_NAME, 'p').get_attribute("innerText").split('—') # Example: Contest ran 16 February 2021—22 February 2021
			df["start"] = ' '.join(dates[0].split(' ')[-3:]) # Remove the 'Contest ran ' and keep only starting date
			df["end"] = dates[1]

			df["prize_money"] = df["prize_money"].str.replace(r'\$|,', '', regex=True).astype(float)
			df["prize_pool"] = round(sum(df["prize_money"]))

			contests_data = pd.concat([contests_data, df])
			logging.info(f"Parsed {contests.index(contest_link) + 1}/{len(contests)} contests ({len(df.index)} rows added) ")
		self.console_handler.terminator = "\n"

		return contests_data.reset_index(drop=True)
