from datetime import timedelta
from decimal import Decimal

import requests

from . import Explorer, explorers


# TODO: No longer needed, remove
def get_outgoing_amount(tx_hash, to_address):
	tx = requests.get(f'https://blockchain.info/rawtx/{tx_hash}').json()
	for outgoing in tx['out']:
		if outgoing['addr'] == to_address:
			return Decimal(outgoing['value']) / Decimal(10**8)


class BitcoinExplorer(Explorer):
	MAX_LIMIT = 50
	ADDRESS_API = 'https://blockchain.info/rawaddr/{address}?limit={limit}&offset={offset}'
	CURRENCY_SLUG = 'bitcoin'

	# TODO: Move logic to data import command
	def get_usd_price(self, timestamp):
		"""
		Returns the price of BTC in USD at given timestamp on Coinbase.

		Note for future: Coinbase's BTC-USD data starts from 2015-01-08 01:24 UTC
		>>> requests.get(
			'https://api.pro.coinbase.com/products/BTC-USD/candles',
			params={
				'start':'2015-01-08T00:00:00Z',
				'end':'2015-01-08T02:00:00Z',
				'granularity':60
			}
		).json()
		[...
		[1420680420, 271.84, 276.34, 271.84, 276.34, 0.02],
		[1420680240, 360, 360, 360, 360, 0.01]]
		
		>>> datetime.fromtimestamp(1420680240, tz=timezone.utc)
		datetime.datetime(2015, 1, 8, 1, 24, tzinfo=datetime.timezone.utc)
		
		Some thoughts on how to calculate the price to return:
		
		The ideal value we want is the "last traded" price, which we don't have
		enough precision to know exactly. Using the open price runs the risk of
		it being an outlier it terms of being representative of the price.
		Smoothing across multiple candles and discarding outliers is probably the
		best approach. Also note that since this is for tax purposes, if we have
		to err (which we do), we should err on the side that favours the taxman.
		Would be interesting to make the chosen approach a setting, and compare
		the final values across different approaches.
		"""
		minute_start = timestamp.replace(second=0, microsecond=0)
		params = {
			'start': minute_start.isoformat(),
			'end': (minute_start + timedelta(seconds=60)).isoformat(),
			'granularity': 60,
		}
		candles = requests.get(
			'https://api.pro.coinbase.com/products/BTC-USD/candles',
			params=params
		)
		time, low, high, open_, close, volume = candles.json(parse_float=Decimal)[0]
		if time != minute_start.timestamp():
			print(f'WARNING: candle start timestamp {time} doesn\'t match '
				f'minute start timestamp {minute_start.timestamp()}')
		return (low + high) / Decimal(2)
		# Or maybe...?
		return open_ + (Decimal(timestamp.timestamp()) - Decimal(minute_pice.timestamp())) / Decimal(60) * (close - open_)

				
# Register the bitcoin explorer
explorers['bitcoin'] = BitcoinExplorer()

