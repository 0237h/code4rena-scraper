# code4rena-github-scraper
Scraping [Code4rena](https://www.code4rena.com) contest audits reports for stats, fun (and profit ?).

For accurate prize money numbers check the Code4rena [leaderboard](https://code4rena.com/leaderboard) directly.

## Why ?

To play around with the [Github API](https://docs.github.com/en/rest) and work my python scripting skills. It also got me working on data analysis tools like [Jupyter notebooks](https://jupyter.org/), [Pandas](https://pandas.pydata.org/docs/index.html) for manipulating the data and the [Altair](https://altair-viz.github.io/index.html) visualization framework.

At first, I was curious since I found out that the audits reports repos contains the address of each participant for sending their prize money (see [here](https://github.com/code-423n4/2021-05-nftx-findings/tree/main/data) for example, in the .json files). It could be an issue if certain people wants to stay anonymous on this platform.

## What ?

Data is scraped from the [Code4rena](https://www.code4rena.com) published audits repos using the [Github API](https://docs.github.com/en/rest) and parsed to a CSV file.

Part of the data extracted can be used to link ETH/Polygon addresses to contest participants. Using tools like [polygonscan](https://polygonscan.com), [etherscan](https://etherscan.io) or [Bitquery](https://explorer.bitquery.io/) allows to look at the flow of funds from and to those wallets.

Is it useful ? Probably not.

Worth the time ? I'd say yes as it gave me insights as to how to track funds accross different chains (Polygon, Ethereum mainnet, etc.).

Also, the extracted data allows to see who might be most efficient, writes the most duplicates, percentage of invalid submission, etc.

## How ?

Use [`code4rena_scraper.py`](code4rena_scraper.py) to fetch and parse the latest data in a .csv file.

Currently, the extracted data looks like this:
| contest_id | handle | address | risk | title | issueId | issueUrl | contest_sponsor | date | tags |
| ---------- | ------ | ------- | ---- | ----- | ------- | -------- | --------------- | ---- | ---- |
| Identifiy the contest | Name of the warden | Polygon address | Caracterize the submission criticity (0 to 3, or G for gas optimization) | Title of the submission | Github issue number | Github issue URL (unused) | Contest sponsor extracted from repo's name | Contest running date extracted from repo's name | Tags associated with issue (further caracterize the submission) |

So each line in the csv file corresponds to one submission (identified by the `issueId`) of a warden (identified by his/her `(handle, address)` pair) for a given contest (identified by the `contest_id`).

Jupyter notebooks can be found in the [charts_data](charts_data/) folder to visualize the data (requires [altair-viz](https://altair-viz.github.io/getting_started/installation.html)).

What's been implemented so far:

- Timeline of wardens participations and bar chart of the number of new participants grouped by their first contest date – *pro tip: drag the mouse on the bar chart to filter for starting dates in the timeline chart*.
![Participant's longevity](charts_data/preview_participants_longevity.png)

- Stacked bar chart which shows the growth of the number of wardens as well as the active (includes brand new wardens), non-participating and inactive proportions of wardens for each month.
![Participant growth](charts_data/preview_participants_growth.png)

## Next ?

- [x] Get linked audits issues tags and add the data to the csv (helps flag invalid, duplicate and accepted submissions)
- [x] Use data analysis modules or external programs to actually do something with the data
- [ ] Connect to Polygon/Ethereum blockchain to show the balances of the addresses listed
- [ ] More notebooks --> more graphs
- [x] ~~Some more data mining from on-chain data maybe (GraphQL API would be best)~~ *won't do, no time*
