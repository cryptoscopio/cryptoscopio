import csv
from datetime import datetime
from decimal import Decimal

from currencio.models import Currency
from currencio.utils import convert

from ..explorers import explorers
from ..models import Event, RecordGroup, Record
from ..utils import wrap_uploaded_file


def parse(data):
	"""
	Coinbase export CSV files have the format:
	
		"Transactions"
		USER, EMAIL, WALLET
		"Account", "CURRENCY Wallet", WALLET
		[blank line]
		[22 column headers]
		[transactions]
	"""
	currency = None
	# TODO: allow this to be set by user
	user_currency = Currency.objects.get(ticker='AUD', fiat=True)
	transactions_parsed = 0
	transactions_skipped = 0
	transactions_failed = 0
	reader = csv.reader(wrap_uploaded_file(data))
	# Skip the first 5 lines that are of no use to us
	[next(reader) for i in range(5)]
	# Parse the data rows
	for timestamp, balance, amount, cryptocurrency, to_, notes, instant, \
		transfer_amount, transfer_currency, transfer_fee, transfer_fee_currency, method, transfer_id, \
		order_price, order_currency, order_btc, order_tracking, order_custom, order_paid, recurring, \
		coinbase_id, blockchain_hash \
	in reader:
		# Check if we've already parsed this transaction
		if Record.objects.filter(platform='coinbase', identifier=coinbase_id).exists():
			transactions_skipped += 1
			continue
		timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S %z')
		amount = Decimal(amount)
		# Currency should stay the same, so avoid re-fetching, but sanity check
		if not currency or currency.ticker != cryptocurrency:
			currency = Currency.objects.get(ticker=cryptocurrency, fiat=False)
			explorer = explorers.get(currency.slug)
		# Cryptocurrency purchase
		if transfer_amount and amount > 0 and transfer_currency:
			# TODO: Handle non-fiat transfer currencies (may be used in GDAX)
			fiat = Currency.objects.get(ticker=transfer_currency, fiat=True)
			price = Decimal(transfer_amount) / amount
			# Create a group to put all the records into
			group = RecordGroup.objects.create(timestamp=timestamp)
			# Create acquisition record and event
			record = Record.objects.create(
				group=group,
				platform='coinbase',
				identifier=coinbase_id,
				timestamp=timestamp,
				amount=amount,
				outgoing=False,
				currency=currency,
				needs_event=False,
			)
			event = Event.objects.create(
				record=record,
				type=Event.ACQUISITION,
				currency=currency,
				amount=amount,
				price=convert(fiat, user_currency, price, timestamp),
			)
			# Create fiat expenditure record
			record = Record.objects.create(
				group=group,
				platform='coinbase',
				identifier=coinbase_id,
				timestamp=timestamp,
				amount=Decimal(transfer_amount),
				outgoing=True,
				currency=fiat,
				needs_event=False,
			)
			# Create fee record
			if transfer_fee and transfer_fee_currency:
				fee_currency = Currency.objects.get(ticker=transfer_currency, fiat=True)
				record = Record.objects.create(
					group=group,
					platform='coinbase',
					identifier=coinbase_id,
					timestamp=timestamp,
					amount=Decimal(transfer_fee),
					outgoing=True,
					currency=fee_currency,
					is_fee=True,
					needs_event=False,
				)
			transactions_parsed += 1
		# Incoming cryptocurrency transfer
		elif not transfer_amount and blockchain_hash and amount > 0:
			# Try to find matching record group if it was sent from own address
			group = RecordGroup.objects.filter(
				records__transaction=blockchain_hash).first()
			# Create one if one wasn't found
			group = group or RecordGroup.objects.create(timestamp=timestamp)
			# Try to find outgoing blockchain transfer with matching amount
			# TODO: Handle outgoing transfers from exchanges, where amount may not match
			existing = group.records.filter(
				transaction=blockchain_hash, currency=currency, amount=amount, outgoing=True)
			# Create the record
			record = Record.objects.create(
				group=group,
				platform='coinbase',
				identifier=coinbase_id,
				transaction=blockchain_hash,
				timestamp=timestamp,
				amount=amount,
				outgoing=False,
				currency=currency,
				needs_event=not existing.exists(),
			)
			# Unset need of event from the first maching outgoing transfer.
			# There's an edge case here where a transaction includes more than
			# one output with the exact same amount going to different 
			# addresses, in which case even if one is marked as a transfer to 
			# own account already, one other will be marked as such. This is 
			# acceptable.
			# TODO: Populate to_address from that transfer?
			existing = existing.filter(needs_event=True).first()
			if existing:
				existing.needs_event = False
				existing.save()
			group.refresh_timestamp()
			transactions_parsed += 1
		# Outgoing cryptocurrency transfer
		elif not transfer_amount and blockchain_hash and to_ and amount < 0:
			# Try to find matching record group if it was sent to own address
			group = RecordGroup.objects.filter(
				records__transaction=blockchain_hash).first()
			# Create one if one wasn't found
			group = group or RecordGroup.objects.create(timestamp=timestamp)
			# Try to find incoming blockchain transfer with matching address
			existing = group.records.filter(
				transaction=blockchain_hash,
				currency=currency,
				to_address=to_,
				amount__lte=-amount,
				outgoing=False,
			).first()
			# Create the record
			record = Record.objects.create(
				group=group,
				platform='coinbase',
				identifier=coinbase_id,
				transaction=blockchain_hash,
				timestamp=timestamp,
				amount=-amount,
				outgoing=True,
				currency=currency,
				to_address=to_,
				needs_event=not existing,
			)
			# If we know this transfer to be to own wallet, the difference
			# between the amount sent and received is the transfer fee, so we 
			# create a record and disposal event for that.
			if existing and not group.records.filter(is_fee=True).exists():
				record = Record.objects.create(
					group=group,
					platform='coinbase',
					identifier=coinbase_id,
					transaction=blockchain_hash,
					timestamp=timestamp,
					amount=-amount - existing.amount,
					outgoing=True,
					currency=currency,
					is_fee=True,
					needs_event=False,
				)
				# TODO: Handle inability to ascertain price
				event = Event.objects.create(
					record=record,
					type=Event.DISPOSAL_FEE,
					currency=currency,
					amount=-amount - existing.amount,
					# TODO: Let convert do the conversion to USD as well
					price=convert(
						Currency.objects.get(ticker='USD', fiat=True),
						user_currency,
						explorer.get_usd_price(timestamp),
						timestamp,
					)
				)
				existing.needs_event = False
				existing.save()
			# TODO: Edge cases:
			#	Simultaneous withdrawal to same address from multiple accounts
			#	User parsed exchange hot wallet as own wallet
			group.refresh_timestamp()
			transactions_parsed += 1
		# Not a recognised type of transaction
		else:
			transactions_failed += 1
			# TODO: log and notify
	return transactions_parsed, transactions_skipped, transactions_failed

