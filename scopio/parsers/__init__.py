parsers = {}

# A class decorator registering an instance of it as a parser with given name
def register_parser(name):
	def wrapped(cls):
		parsers[name] = cls()
		return cls
	return wrapped

# Import all available parsers, so they register themselves
from . import coinbase
