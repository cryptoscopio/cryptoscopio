from collections import defaultdict
from datetime import timedelta
from hashlib import sha256
import json

from django.utils.timezone import now

from ..explorers.bitcoin import BitcoinExplorer


def generate_bitcoin_address(self, key):
	"""
	Return a valid Bitcoin address for a given public key, using a distant
	approximation of how Bitcoin does it, because why not?

	Ideally, the first line should be replaced by:

		address = hashlib.new('ripemd-160');
		address.update(hashlib.sha256(key.encode('utf-8').digest())
		address = b'\x00' + address.digest()

	But to avoid needlessly requiring Python to be compiled against an OpenSSL
	version	with RIPEMD-160 support, we just use the first 20 bytes of the
	SHA-256 hash instead.
	"""
	# Get a 20-byte hash of the key and append the version byte
	address = b'\x00' + sha256(key.encode('utf-8').digest()[:20]
	# Calculate and append the checksum
	address += sha256(sha256(address).digest()).digest()[:4]
	# Count leading zeroes
	leading = len(address) - len(address.lstrip(b'\x00'))
	# Convert to an integer
	address = int.from_bytes(address, 'big')
	# Encode to Base58
	encoded = ''
	base58_map = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
	while address:
		address, remainder = divmod(address, 58)
		encoded = base58_map[remainder] + encoded
	# Add leading zeroes (1 in Base58) back
	encoded = '1' * leading + encoded
	return encoded


class TestBitcoinExplorer(BitcoinExplorer):
	"""
	Provides an emulated Bitcoin blockchain where arbitrary transactions can
	be added for testing purposes. Overrides `transactions_for_address` method
	to return those transactions in the same manner as `BitcoinExplorer` would,
	i.e. using the same key names as the blockchain.info API JSON dicts.
	"""

	def __init__(self):
		# A mapping of addresses to transactions that involve the address as
		# either an input or output, in reverse chronological order
		self._addresses = defaultdict(list)

	def send(self, inputs, outputs):
		"""
		Takes a list of inputs (as returned as outputs by a previous send()
		call), and a list of outputs, which are tuples of (amount, address),
		and creates a transaction spending the input to generate the outputs.
		Returns the transaction hash and a list of generated outputs.
		"""
		# Pretend it's yesterday so real-time price look-ups don't fail.
		# TODO: Remove this once we're no longer using real-time lookups
		timestamp = (now() - timedelta(1)).timestamp()
		# We rely on transaction being mutable, since we continue modifying it
		# after adding it to the transaction lists for the addresses involved
		transaction = {'inputs': [], 'out': [], 'time': timestamp}
		# Add the inputs to the transaction and associate it with the
		# destination addresses in the inputs
		for input_ in inputs:
			transaction['inputs'] += [{'prev_out': input_}]
			self._addresses[input_['addr']].insert(0, transaction)
		# Add the outputs to the transaction and associate it with the
		# destination addresses of the outputs
		for index, (amount, address) in enumerate(outputs):
			transaction['out'] += [{
				'addr': address, 'value': int(amount), 'n': index }]
			# Avoid duplicate records when sending to same address as input
			if transaction not in self._addresses[address]:
				self._addresses[address].insert(0, transaction)
		# Distant approximation of what Bitcoin does to get tx hash, kinda
		# pointless, but why not?
		transaction['hash'] = \
			sha256(json.dumps(transaction).encode('utf-8')).hexdigest()
		return transaction['hash'], transaction['out']

	def transactions_for_address(self, address):
		return self._addresses[address]

