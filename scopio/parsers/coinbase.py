import csv
from datetime import datetime
from decimal import Decimal

from .. import explorers
from ..models import Event, Record
from ..utils import wrap_uploaded_file


def parse(data):
	"""
	Coinbase export CSV have the format:
	
		"Transactions"
		USER, EMAIL, WALLET
		"Account", "CURRENCY Wallet", WALLET
		[blank line]
		[22 column headers]
		[transactions]
	"""
	transactions_parsed = 0
	transactions_skipped = 0
	transactions_failed = 0
	reader = csv.reader(wrap_uploaded_file(data))
	# Skip the first 5 lines that are of no use to us
	[next(reader) for i in range(5)]
	# Parse the data rows
	for timestamp, balance, amount, currency, to_, notes, instant, \
		transfer_amount, transfer_currency, transfer_fee, transfer_fee_currency, method, transfer_id, \
		order_price, order_currency, order_btc, order_tracking, order_custom, order_paid, recurring, \
		coinbase_id, blockchain_hash \
	in reader:
		id_ = f'coinbase {coinbase_id}'
		# Check if we've already parsed this transaction
		if Record.objects.filter(pk=id_).exists():
			transactions_skipped += 1
			continue
		timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S %z')
		amount = Decimal(amount)
		# Cryptocurrency purchase
		if transfer_amount and amount > 0 and transfer_currency == 'AUD':
			# The fee is not included in the price calculation
			price = (Decimal(transfer_amount) - Decimal(transfer_fee or 0)) / amount
			# TODO: convert price to the user's currency, if needed
			record = Record.objects.create(
				pk=id_,
				timestamp=timestamp,
				amount=amount,
				currency=currency,
				price=price,
				fiat=transfer_currency,
			)
			# Create acquisition tax event
			event = Event.objects.create(
				type=Event.ACQUISITION,
				timestamp=timestamp,
				currency=currency,
				amount=amount,
				price=price,
			)
			record.events.add(event)
			# Create a non-tax event for the fee that was paid
			if transfer_fee and Decimal(transfer_fee) > 0:
				event = Event.objects.create(
					type=Event.FIAT_FEE,
					timestamp=timestamp,
					currency=transfer_currency,
					amount=Decimal(transfer_fee),
					price=None,
				)
				record.events.add(event)
			transactions_parsed += 1
		# Incoming cryptocurrency transfer
		elif not transfer_amount and amount > 0:
			record = Record.objects.create(
				pk=id_,
				timestamp=timestamp,
				amount=amount,
				currency=currency,
				tx_hash=blockchain_hash,
			)
			transactions_parsed += 1
		# Outgoing cryptocurrency transfer
		elif not transfer_amount and amount < 0:
			record = Record.objects.create(
				pk=id_,
				timestamp=timestamp,
				amount=amount,
				currency=currency,
				tx_hash=blockchain_hash,
			)
			# The transfer fee is not specified, so we get it from the blockchain.
			# There is a small risk here for currencies such as Bitcoin, where
			# transaction has multiple inputs/outputs, of someone else making
			# a transfer to the same address within the same transaction.
			# TODO: use matching explorer for currency
			received = -explorers.bitcoin.get_outgoing_amount(blockchain_hash, to_)
			# Keep in mind amount and received should be negative
			if received and received > amount:
				event = Event.objects.create(
					type=Event.DISPOSAL_FEE,
					timestamp=timestamp,
					currency=currency,
					amount=amount - received,
					# TODO: convert USD to local currency
					price=explorers.bitcoin.get_usd_price(timestamp),
				)
				record.events.add(event)
			transactions_parsed += 1
		# Not a recognised type of transaction
		else:
			transactions_failed += 1
			# TODO: log and notify
	return transactions_parsed, transactions_skipped, transactions_failed

