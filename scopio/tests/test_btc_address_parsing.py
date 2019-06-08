from decimal import Decimal

from django.test import TestCase

from .utils import TestBitcoinExplorer
from ..explorers import explorers
from ..models import RecordGroup, Record, Event


class ParseBitcoinAddressTestCase(TestCase):
	"""
	A set of tests for the BitcoinExplorer's parse_address() functionality,
	checking that the expected RecordGroups, Records, and Events are created,
	and that records are correctly matched with each other when appropriate.
	
	"Matching" in this context generally means that `needs_event` is False.
	"""

	fixtures = ['initial']

	def setUp(self):
		# Replace the Bitcoin explorer with our emulated one
		self.old_explorer = explorers['bitcoin']
		explorers['bitcoin'] = TestBitcoinExplorer()

	def tearDown(self):
		# Restore the original Bitcoin explorer
		explorers['bitcoin'] = self.old_explorer

	def test_basic_matching(self):
		# Mine 10 BTC to address A, send 3 BTC each to B, C and D
		_, (mine_10_to_a,) = explorers['bitcoin'].send([], [(10e8, 'a')])
		explorers['bitcoin'].send(
			[mine_10_to_a], [(3e8, 'b'), (3e8, 'c'), (3e8, 'd'),])
		# Parse address A as own address
		explorers['bitcoin'].parse_address('a')
		# Check that all expected records have been created
		self.assertEqual(RecordGroup.objects.count(), 2)
		self.assertEqual(Record.objects.count(), 5)
		# Incoming mined 10 BTC with base cost of zero
		Record.objects.get(
			amount=Decimal(10),
			outgoing=False,
			is_fee=False,
			to_address='a',
			needs_event=False,
			event__type=Event.ACQUISITION,
			event__price=Decimal(0),
		)
		# Unmatched outgoing transfers of 3 BTC each
		Record.objects.get(
			amount=Decimal(3),
			outgoing=True,
			is_fee=False,
			to_address='b',
			needs_event=True,
			event__isnull=True,
		)
		Record.objects.get(
			amount=Decimal(3),
			outgoing=True,
			is_fee=False,
			to_address='c',
			needs_event=True,
			event__isnull=True,
		)
		Record.objects.get(
			amount=Decimal(3),
			outgoing=True,
			is_fee=False,
			to_address='d',
			needs_event=True,
			event__isnull=True,
		)
		# Outgoing fee of 1 BTC, with a disposal event with an unset price,
		# indicating a price lookup was attempted, but failed.
		Record.objects.get(
			amount=Decimal(1),
			outgoing=True,
			is_fee=True,
			to_address='',
			needs_event=False,
			event__isnull=False,
			event__type=Event.DISPOSAL_FEE,
			event__price__isnull=True,
		)
		# Now "reveal" that address C is also an own address
		explorers['bitcoin'].parse_address('c')
		# Check that the expected incoming record was created
		self.assertEqual(RecordGroup.objects.count(), 2)
		self.assertEqual(Record.objects.count(), 6)
		self.assertEqual(Record.objects.filter(needs_event=True).count(), 2)
		Record.objects.get(
			amount=Decimal(3),
			outgoing=False,
			is_fee=False,
			to_address='c',
			needs_event=False,
			event__isnull=True,
		)
		# Check that the outgoing transfer has been matched
		Record.objects.get(
			amount=Decimal(3),
			outgoing=True,
			is_fee=False,
			to_address='c',
			needs_event=False,
			event__isnull=True,
		)

	def test_no_fee_transaction(self):
		# Mine 10 BTC to address A, send 5 each to B and C
		_, (mine_10_to_a,) = explorers['bitcoin'].send([], [(10e8, 'a')])
		explorers['bitcoin'].send([mine_10_to_a], [(5e8, 'b'), (5e8, 'c'),])
		# Parse address A as own address
		explorers['bitcoin'].parse_address('a')
		self.assertEqual(RecordGroup.objects.count(), 2)
		self.assertEqual(Record.objects.count(), 3)
		self.assertEqual(Record.objects.filter(needs_event=True).count(), 2)
		# Check that no fee record was created
		self.assertEqual(Record.objects.filter(is_fee=True).count(), 0)

	def test_same_address_transfer(self):
		# Mine 10 BTC to address A, send 5 each to A and B
		_, (mine_10_to_a,) = explorers['bitcoin'].send([], [(10e8, 'a')])
		explorers['bitcoin'].send([mine_10_to_a], [(5e8, 'a'), (5e8, 'b'),])
		# Parse address A as own address
		explorers['bitcoin'].parse_address('a')
		# Check that both incoming and outgoing records exist for the transfer
		# and that they are matched
		self.assertEqual(RecordGroup.objects.count(), 2)
		self.assertEqual(Record.objects.count(), 4)
		Record.objects.get(
			amount=Decimal(5),
			outgoing=True,
			is_fee=False,
			to_address='a',
			needs_event=False,
			event__isnull=True,
		)
		Record.objects.get(
			amount=Decimal(5),
			outgoing=False,
			is_fee=False,
			to_address='a',
			needs_event=False,
			event__isnull=True,
		)

	def test_multiple_inputs(self):
		# Mine 10 BTC to address A, send 4 to A and 5 to B, pay fee of 1
		_, (mine_10_to_a,) = explorers['bitcoin'].send([], [(10e8, 'a')])
		_, outputs = explorers['bitcoin'].send(
			[mine_10_to_a], [(4e8, 'a'), (5e8, 'b'),])
		# Send 7 BTC to address D, using both outputs from above, pay fee of 2
		explorers['bitcoin'].send(outputs, [(7e8, 'd'),])
		# Parse address B as own address
		# TODO: Check that A is suggested as an own address
		explorers['bitcoin'].parse_address('b')
		# Check that all expected records have been created
		self.assertEqual(RecordGroup.objects.count(), 2)
		self.assertEqual(Record.objects.count(), 3)
		Record.objects.get(
			amount=Decimal(5),
			outgoing=False,
			is_fee=False,
			to_address='b',
			needs_event=True,
			event__isnull=True,
		)
		Record.objects.get(
			amount=Decimal(7),
			outgoing=True,
			is_fee=False,
			to_address='d',
			needs_event=True,
			event__isnull=True,
		)
		Record.objects.get(
			amount=Decimal(2),
			outgoing=True,
			is_fee=True,
			to_address='',
			needs_event=False,
			event__isnull=False,
			event__type=Event.DISPOSAL_FEE,
			event__price__isnull=True,
		)


"""
Parse incoming exchange transfer with tx "tx1" and amount "a1".
Create transaction with two outputs, to "addr1" and "addr2", both with amount "a1".
Parse address that includes that transaction.
Output to "addr1" will be matched with the incoming exchange transfer and have needs_event=False.
Output to "addr2" will have needs_event=True.
Parse "addr1" as own address.
Output to "addr2" should now have needs_event=False.
	The output to "addr1" should be unmatched from exchange transfer, and matched with incoming transfer to "addr2".
	The output to "addr2" should be matched to exchange transfer.

Parse two incoming exchange transfers, both with amount "a1" and tx "tx1".
Create transaction with two outputs for to "addr1" and amount "a1".
Parse address that includes that transaction as outgoing.
Assert that both incoming exchange transfers have been matched with the outputs.

Parse incoming exchange transfer with amount "a1" and "tx1".
Create transaction with output of "a1" to address "addr1".
Have the user mark the exchange transfer as from own address, but refuse to parse the address.
Parse address that includes that transaction as outgoing.
Assert that the output has not been matched, because the onus is now on the user to match them.
"""
