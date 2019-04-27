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

	def handle(self, *args, **options):
		try:
			source = Currency.objects.get(ticker=options['source'].upper(), fiat=True)
		except Currency.DoesNotExist:
			raise CommandError(f'Currency "{options["source"]}" has no database record')
		try:
			target = Currency.objects.get(ticker=options['target'].upper(), fiat=True)
		except Currency.DoesNotExist:
			raise CommandError(f'Currency "{options["target"]}" has no database record')
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
				# Discard pre-2009 records, before cryptocurrency existed
				if timestamp < datetime(2019, 1, 1).timestamp():
					continue
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
