import requests

from currencio.models import Currency


class Explorer:
	def get_json(self, url):
		# TODO: retry on failure
		return requests.get(url).json()

	@property
	def currency(self):
		if not hasattr(self, '_currency'):
			self._currency = Currency.objects.get(slug=self.CURRENCY_SLUG)
		return self._currency


explorers = {}

# A class decorator registering an instance of it as an explorer with given name
def register_explorer(name):
	def wrapped(cls):
		explorers[name] = cls()
		return cls
	return wrapped

# Import all available explorers, so they register themselves
from . import bitcoin
