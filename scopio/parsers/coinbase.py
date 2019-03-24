import csv
from datetime import datetime
from decimal import Decimal

from ..models import Record
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
		id_ = 'CBASE%s' % coinbase_id
		# Check if we've already parsed this transaction
		if Record.objects.filter(pk=id_).exists():
			transactions_skipped += 1
			continue
		timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S %z')
		amount = Decimal(amount)
		# TODO: check if transfer currency matches the user's currency and convert if not
		if transfer_amount and amount > 0 and transfer_currency == 'AUD':
			# Cryptocurrency purchase
			record = Record.objects.create(
				pk=id_,
				timestamp=timestamp,
				amount=amount,
				currency=currency,
				price=Decimal(transfer_amount) / amount,
				fiat=transfer_currency,
			)
			transactions_parsed += 1
		elif not transfer_amount and amount > 0:
			# Incoming cryptocurrency transfer
			record = Record.objects.create(
				pk=id_,
				timestamp=timestamp,
				amount=amount,
				currency=currency,
				tx_hash=blockchain_hash,
			)
			transactions_parsed += 1
		elif not transfer_amount and amount < 0:
			# Outgoing cryptocurrency transfer
			record = Record.objects.create(
				pk=id_,
				timestamp=timestamp,
				amount=amount,
				currency=currency,
				tx_hash=blockchain_hash,
			)
			transactions_parsed += 1
		else:
			# Not a recognised type of transaction
			transactions_failed += 1
			# TODO: log and notify
	return transactions_parsed, transactions_skipped, transactions_failed

