# code4rena-github-scraper
Scraping contest audits reports for stats, fun (and profit ?).

For accurate numbers check the Code4rena [leaderboard](https://code4rena.com/leaderboard) directly.

## Why ?

To play around with the [Github API](https://docs.github.com/en/rest) and work my python scripting skills. I was curious since I found out that the audits reports repos contains the address of each participant for sending their prize money (see [here](https://github.com/code-423n4/2021-05-nftx-findings/tree/main/data) for example, in the .json files).

It can be an issue if certain people wants to stay anonymous on this platform. 

## What ?

Data is scraped from the [Code4rena](https://www.code4rena.com) published audits repos using the [Github API](https://docs.github.com/en/rest) and parsed to a CSV file.

The data extracted, although much more accurate and directly available from the [leaderboard](https://code4rena.com/leaderboard) at Code4rena, can be used to link addresses to contest participants. Using tools like [polygonscan](https://polygonscan.com), [etherscan](https://etherscan.io) or [Bitquery](https://explorer.bitquery.io/) allows to look at the flow of funds from and to those wallets.

Is it useful ? Probably not.

Worth the time ? I'd say yes as it gave me insights as to how to track funds accross different chains (Polygon, Ethereum mainnet, etc.).

## Next ?

- [ ] Get linked audits issues tags and add the data to the csv (helps flag invalid, duplicate and accepted submissions)
- [ ] Connect to Polygon/Ethereum blockchain to show the balances of the addresses listed
- [x] ~~Some more data mining from on-chain data maybe (GraphQL API would be best)~~ *won't do, no time*