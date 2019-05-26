import requests

from currencio.models import Currency


class Explorer(object):
	def get_json(self, url):
		# TODO: retry on failure
		return requests.get(url).json()

	@property
	def currency(self):
		if not hasattr(self, '_currency'):
			self._currency = Currency.objects.get(slug=self.CURRENCY_SLUG)
		return self._currency


explorers = {}


# Import all available explorers, so they register themselves
from . import bitcoin
