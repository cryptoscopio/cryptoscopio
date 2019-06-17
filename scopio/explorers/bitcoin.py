from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import reduce
from hashlib import sha256

import requests

from currencio.models import Currency
from currencio.utils import convert

from . import Explorer, register_explorer
from ..models import Event, Record, RecordGroup


# TODO: No longer needed, remove
def get_outgoing_amount(tx_hash, to_address):
	tx = requests.get(f'https://blockchain.info/rawtx/{tx_hash}').json()
	for outgoing in tx['out']:
		if outgoing['addr'] == to_address:
			return Decimal(outgoing['value']) / Decimal(10**8)


@register_explorer('bitcoin')
class BitcoinExplorer(Explorer):
	MAX_LIMIT = 50
	ADDRESS_API = 'https://blockchain.info/rawaddr/{address}?limit={limit}&offset={offset}'
	CURRENCY_SLUG = 'bitcoin'
	DISPLAY_NAME = 'Bitcoin'

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

	def validate_address(self, address):
		"""
		Validate whether provided address is a valid Bitcoin public address
		that we're able to query transactions for. Returns informative error 
		message if validation fails, or None if it succeeds.
		"""
		base58_map = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
		# The blockchain.info explorer doesn't index Bech32 addresses
		# introduced with SegWit, so we can't query their transactions. If we 
		# want to support them, there are other explorers we can use instead:
		# https://en.bitcoin.it/wiki/Bech32_adoption#Blockchain_Explorers
		if address.startswith('bc1'):
			return 'Bech32 addresses are not currently supported'
		# See this reference for possible address prefixes:
		# https://en.bitcoin.it/wiki/List_of_address_prefixes
		if not address[0] in '13':
			return 'Address is not a mainnet public key or script'
		# Rudimentary validity checks
		if not set(address).issubset(base58_map):
			return 'Address contains invalid characters'
		if len(address) > 34 or len(address) < 26:
			return 'Address length is not within a valid range'
		# Calculate and verify the checksum, see here for more info:
		# https://en.bitcoin.it/wiki/Technical_background_of_version_1_Bitcoin_addresses
		decoded = reduce(
			lambda prev, next: prev * 58 + base58_map.index(next), address, 0
		).to_bytes(25, 'big')
		checksum = sha256(sha256(decoded[:-4]).digest()).digest()[:4]
		if decoded[-4:] != checksum[:4]:
			return 'Address failed integrity checks, may be mistyped'
		return None

	def transactions_for_address(self, address):
		"""
		An iterator of transaction dictionaries for the provided public
		Bitcoin address.
		"""
		offset = 0
		while True:
			data = self.get_json(self.ADDRESS_API.format(
				address=address,
				limit=self.MAX_LIMIT,
				offset=offset,
			))
			for transaction in data['txs']:
				yield transaction
			if len(data['txs']) < self.MAX_LIMIT:
				break
			offset += self.MAX_LIMIT

	def parse_address(self, address):
		"""
		Create Records for the transactions associated with the provided public
		Bitcoin address.
		"""
		# Other public addresses likely to represent the same private key, 
		# deduced from transaction inputs
		# TODO: Suggest importing these other addresses
		other_addresses = set()
		for transaction in self.transactions_for_address(address):
			input_addresses = [
				input_['prev_out']['addr'] \
				for input_ in transaction['inputs'] if 'prev_out' in input_
			]
			total_input = sum(
				input_['prev_out']['value'] \
				for input_ in transaction['inputs'] if 'prev_out' in input_
			)
			total_output = sum(o['value'] for o in transaction['out'])
			timestamp=datetime.fromtimestamp(transaction['time'], tz=timezone.utc)
			# Try to find existing record group for this transaction
			group = RecordGroup.objects.filter(
				records__transaction=transaction['hash']).first()
			# Create one if one wasn't found
			group = group or RecordGroup.objects.create(timestamp=timestamp)
			if address in input_addresses:
				# If the transaction is drawing from an input that was sent to 
				# this address, we consider it an outgoing transfer, because it
				# indicates that the initiator of this transaction has access
				# to the private key for that address (or similar authority).
				for output in transaction['out']:
					# Check if we've parsed this transaction output before as 
					# an outgoing transfer
					if Record.objects.filter(
						transaction=transaction['hash'],
						currency=self.currency,
						outgoing=True,
						identifier=output['n'],
					).exists():
						continue
					amount = Decimal(output['value']) / Decimal(10 ** 8)
					# Check for a matching incoming transfer on a parsed address
					existing = group.records.filter(
						transaction=transaction['hash'],
						currency=self.currency,
						outgoing=False,
						identifier=output['n'],
					)
					if not existing:
						# Check for a matching incoming transfer on an exchange.
						# If the amounts don't match due to an incoming fee, 
						# it's up to the user to match them, which is when a
						# record for that fee will be created.
						existing = group.records.filter(
							transaction=transaction['hash'],
							currency=self.currency,
							amount=amount,
							outgoing=False,
							platform__gt='',
						)
					# Create a record for this transaction output
					record = Record.objects.create(
						timestamp=timestamp,
						group=group,
						currency=self.currency,
						amount=amount,
						outgoing=True,
						transaction=transaction['hash'],
						to_address=output['addr'],
						identifier=output['n'],
						needs_event=not existing,
					)
					if existing:
						# There's a rabbit hole of an edge case here when there
						# are multiple outputs of the same amount going to an
						# exchange. We gloss over it by marking the first
						# unmatched possible match as a match.
						existing = existing.filter(needs_event=True).first()
						if existing:
							existing.needs_event = False
							existing.save()
				# Create a record and event for the transaction fee
				tx_fee = Decimal(total_input - total_output) / Decimal(10 ** 8)
				if tx_fee and not group.records.filter(
					currency=self.currency, amount=tx_fee, is_fee=True,
				).exists():
					record = Record.objects.create(
						timestamp=timestamp,
						group=group,
						currency=self.currency,
						amount=tx_fee,
						outgoing=True,
						transaction=transaction['hash'],
						is_fee=True,
						needs_event=False,
					)
					event = Event.objects.create(
						type=Event.DISPOSAL_FEE,
						record=record,
						currency=self.currency,
						amount=tx_fee,
						# TODO: Move price calculation to a context with user currency access
						price=convert(
							Currency.objects.get(ticker='USD', fiat=True),
							Currency.objects.get(ticker='AUD', fiat=True),
							self.get_usd_price(timestamp),
							timestamp,
						)
					)
				# Any other addresses appearing in the inputs are likely to be
				# alternate keys from the same wallet, since the user 
				# initiating this transaction was able to draw from them.
				# TODO: Filter out addresses we've already parsed
				other_addresses |= set(input_addresses) - set([address])
			# Go through the outputs again, this time looking for matching
			# destination addresses, and parse those as incoming transfers.
			# Not using an `else` here ensures that any transfers to the same 
			# address as the sender are parsed both as outgoing and incoming.
			for output in transaction['out']:
				# Only the output sent to this address is relevant, there may
				# be many others to other addresses. No address is specified
				# for null data transactions.
				if 'addr' in output and output['addr'] == address:
					# Check if we've parsed this transaction output before as 
					# an incoming transfer
					if Record.objects.filter(
						transaction=transaction['hash'],
						currency=self.currency,
						outgoing=False,
						identifier=output['n'],
					).exists():
						continue
					amount = Decimal(output['value']) / Decimal(10 ** 8)
					# Check for a matching outgoing transfer on a parsed address
					existing = group.records.filter(
						transaction=transaction['hash'],
						currency=self.currency,
						outgoing=True,
						identifier=output['n'],
					).first()
					if not existing:
						# Check for a matching outgoing transfer on an exchange.
						# It will be common for the amount to be larger on such
						# a match, since exchanges include tranfer fees as part
						# of the amount in an export.
						existing = group.records.filter(
							transaction=transaction['hash'],
							currency=self.currency,
							to_address=address,
							outgoing=True,
							platform__gt='',
							amount__gte=amount,
						).first()
					# Create a record for this transaction output
					record = Record.objects.create(
						timestamp=timestamp,
						group=group,
						currency=self.currency,
						amount=amount,
						outgoing=False,
						transaction=transaction['hash'],
						to_address=address,
						identifier=output['n'],
						needs_event=bool(input_addresses) and not existing,
					)
					# Check if this was a mining reward and create zero-cost 
					# acquisition event if it is
					if not input_addresses:
						event = Event.objects.create(
							type=Event.ACQUISITION,
							record=record,
							currency=self.currency,
							amount=amount,
							price=Decimal(0),
						)
					if existing and amount < existing.amount \
					and not group.records.filter(
						currency=self.currency,
						amount=existing.amount - amount,
						is_fee=True,
					).exists():
						# If we found a matching outgoing transfer from an
						# exchange, but its amount is larger, we consider the
						# difference as the transfer fee and create a record.
						record = Record.objects.create(
							timestamp=timestamp,
							group=group,
							currency=self.currency,
							amount=existing.amount - amount,
							outgoing=True,
							transaction=transaction['hash'],
							is_fee=True,
							needs_event=False,
						)
						event = Event.objects.create(
							type=Event.DISPOSAL_FEE,
							record=record,
							currency=self.currency,
							amount=existing.amount - amount,
							# TODO: Move price calculation to a context with user currency access
							price=convert(
								Currency.objects.get(ticker='USD', fiat=True),
								Currency.objects.get(ticker='AUD', fiat=True),
								self.get_usd_price(timestamp),
								timestamp,
							)
						)
					# TODO: Edge case where two outputs with the same amount
					# are sent to an exchange and to own address, but own 
					# address is parsed after the exchange. This can end up 
					# matching the first output to both the exchange and own 
					# wallet, leaving the second output unmatched.
					if existing:
						existing.needs_event = False
						existing.save()
			group.refresh_timestamp()

