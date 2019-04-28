from datetime import datetime, timezone
from decimal import Decimal
import struct

from django.core.management.base import BaseCommand, CommandError

from ...models import Currency, Pair, MovementData


class Command(BaseCommand):
	help = 'Load movement data from FXDD historic data HST file obtained from: ' \
		'https://www.fxdd.com/mt/en/resources/mt4-one-minute-data'

	def add_arguments(self, parser):
		parser.add_argument('source', help='Source currency (e.g. AUD)')
		parser.add_argument('target', help='Target currency (e.g. USD)')
		parser.add_argument('hst_file', help='Path to HST file')
		parser.add_argument('--from-date', help='Date to parse data from (e.g. 2009-01-14)')
		parser.add_argument('--to-date', help='Date to parse data from (e.g. 2018-06-31)')

	def handle(self, *args, **options):
		try:
			source = Currency.objects.get(ticker=options['source'].upper(), fiat=True)
		except Currency.DoesNotExist:
			raise CommandError(f'Currency "{options["source"]}" has no database record')
		try:
			target = Currency.objects.get(ticker=options['target'].upper(), fiat=True)
		except Currency.DoesNotExist:
			raise CommandError(f'Currency "{options["target"]}" has no database record')

		from_date = None
		if 'from_date' in options:
			try:
				from_date = datetime.strptime(options['from_date'], '%Y-%m-%d')
			except ValueError:
				raise CommandError(f'Could not parse from date "{options["from_date"]}" into date')
		to_date = None
		if 'to_date' in options:
			try:
				to_date = datetime.strptime(options['to_date'], '%Y-%m-%d')
			except ValueError:
				raise CommandError(f'Could not parse from date "{options["to_date"]}" into date')
		with open(options['hst_file'], 'rb') as f:
			# Skip header
			f.read(148)
			# Now that we've established that the file exists, create the Pair object
			pair, _ = Pair.objects.get_or_create(
				source=source,
				target=target,
				granularity=60,
				data_source='FXDD',
			)
			# Read and parse the entries
			records_parsed = records_added = 0
			while True:
				buffer = f.read(44)
				if not buffer:
					break
				timestamp, open_, high, low, close, volume = struct.unpack("<iddddd", buffer)
				# Discard records outside of specified range
				if from_date and timestamp < from_date.timestamp():
					continue
				if to_date and timestamp > to_date.timestamp():
					continue
				# Create records without overwriting existing ones
				record, created = MovementData.objects.get_or_create(
					pair=pair,
					timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
					defaults={
						'open': Decimal(open_),
						'high': Decimal(high),
						'low': Decimal(low),
						'close': Decimal(close),
						'volume': Decimal(volume),
					}
				)
				if created:
					records_added += 1
				records_parsed += 1
				if not records_parsed % 1000000:
					self.stdout.write(f'{records_parsed} records parsed...')
			# Update record timespan on pair
			pair.update_timespan()
			self.stdout.write(f'Done. {records_parsed} records parsed, {records_added} new records added.')
