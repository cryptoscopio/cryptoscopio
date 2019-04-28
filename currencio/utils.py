from collections import defaultdict
from decimal import Decimal
from functools import reduce

from django.db import models

from .models import MovementData, Pair


MAX_SEARCH_DEPTH = 5

def _find_paths(source, target, timestamp, depth=0, seen=[], path=[]):
	"""
	Recursive iterator that yields lists of trading pairs that provide a path 
	from the source to target currency, where movement data is available for 
	the given timestamp. Favours pairs with lower granularity if multiple pairs
	between two given currencies are available. Does not search for paths
	longer than `MAX_SEARCH_DEPTH` hops.
	"""
	if depth > MAX_SEARCH_DEPTH:
		return
	# Make sure we don't loop back to the starting currency
	if not seen:
		seen = [source]
	links = defaultdict(list)
	# Find pairs that have source currency as either the source or the target
	# curency, excluding ones where the other currency is one we've hopped from
	# before, and excluding pairs that have no movement data for the timestamp.
	for pair in Pair.objects.filter(
		source=source,
		earliest_data__lte=timestamp
	).exclude(target__in=seen):
		if pair.latest_data.timestamp() >= timestamp.timestamp() - pair.granularity:
			links[pair.target] += [pair]
	for pair in Pair.objects.filter(
		target=source,
		earliest_data__lte=timestamp
	).exclude(source__in=seen):
		if pair.latest_data.timestamp() >= timestamp.timestamp() - pair.granularity:
			links[pair.source] += [pair]
	# In case of multiple pairs to target currency found, use the first one 
	# with lowest granularity.
	if target in links:
		finest = sorted(links[target], key=lambda x: x.granularity)[0]
		yield path + [finest]
	else:
		for new_source, pairs in links.items():
			# Use pair with lowest granularity to construct path found so far
			finest = sorted(pairs, key=lambda x: x.granularity)[0]
			for new_path in _find_paths(
				new_source, target, timestamp,
				depth=depth + 1,
				seen=seen + list(links.keys()),
				path=path + [finest]
			):
				yield new_path


class PathNotFound(Exception):
	pass


def convert(source, target, amount, timestamp):
	# Check for no-op
	if source == target:
		return amount
	# Find paths from source to target currency via trading pairs with
	# available movement data
	paths = list(_find_paths(source, target, timestamp))
	if not paths:
		raise PathNotFound()
	# Trim down results to the one(s) with fewest conversions
	min_length = len(sorted(paths, key=len)[0])
	paths = [path for path in paths if len(path) == min_length]
	# Pick the first (for lack of better metrics) of the remaining paths with 
	# the lowest cumulative granularity
	path = sorted(paths,
		key=lambda path: reduce(int.__add__, (pair.granularity for pair in path))
	)[0]
	# Hop through the pairs in the path, converting the amount until it's in 
	# the target currency
	for pair in path:
		if source == pair.source:
			amount = amount * pair.price_at(timestamp)
			source = pair.target
		else:
			amount = amount / pair.price_at(timestamp)
			source = pair.source
		if source == target:
			return amount

