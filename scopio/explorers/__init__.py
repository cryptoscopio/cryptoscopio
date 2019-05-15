import requests

class Explorer(object):
	def get_json(url):
		# TODO: retry on failure
		return requests.get(url).json()

explorers = {}

# Import all available explorers, so they register themselves
from . import bitcoin
