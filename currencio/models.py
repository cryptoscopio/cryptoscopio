import decimal

from django.db import models
from django.utils.formats import get_format, number_format


class Currency(models.Model):
	slug = models.CharField(max_length=128, primary_key=True)
	ticker = models.CharField(max_length=64)
	name = models.CharField(max_length=256)
	fiat = models.BooleanField()
	prefix = models.CharField(max_length=4, blank=True)
	precision = models.PositiveIntegerField(null=True)

	class Meta:
		verbose_name_plural = 'currencies'

	def __str__(self):
		return self.name or self.ticker or self.slug

	def get_short_name(self):
		return self.ticker or self.slug

	def format_amount(self, amount, max_decimals=8):
		"""
		Return a human-friendly representation of the amount in this currency,
		rounding the number to include only `max_decimals` significant digits 
		after the decimal point, or the currency's precision if specified and
		smaller.
		
		Ideally, most of this could be accomplished using Decimal.quantize() 
		and Decimal.normalize(); however, Python insists on using exponential
		notation when it can remove more than 5 zeroes from the number, e.g.:
		
		>>> 0.00001
		1e-5
		>>> 0.00012
		0.00012
		
		We also can't rely on "%f" string formatting, because it casts the 
		value to a float first, introducing floating-point errors:

		>>> '%.20f' % decimal.Decimal('0.1')
        '0.10000000000000000555'

		So we resort to using the components returned by Decimal.as_tuple().

		Django's number_format function would do most of the work for us,
		except it relies on "%f", so we can only use it for formatting the
		part of the number preceding the decimal point.

		Ideally, we would want to use the GLIBC locale definitions for 
		formatting, which include many niceties, see:
		https://docs.python.org/3/library/locale.html#locale.localeconv

		However, Python only allows the local conventions to be fetched for 
		the current locale, and switching locales is advised against, since 
		it isn't thread-safe. So we make do with Django's built-in L10N for 
		now, as well as some AU-centric conventions, and may revisit this in 
		the future.

		Useful reference for the GLIBC locale data:
		https://lh.2xlibre.net/locales/
		"""
		sign, digits, exponent = amount.normalize().as_tuple()
		# Count the number of zeroes after the decimal point until first 
		# non-zero digit
		if -exponent + 1 > len(digits):
			# For numbers smaller than one, derive from the exponent
			zeroes = -exponent - len(digits) + 1
		else:
			# Otherwise, convert the digits after the decimal point into a 
			# string, strip leading zeroes, and use the difference of the 
			# resulting length from the original length
			zeroes = len(digits[exponent:]) \
				- len(''.join(map(str, digits[exponent:])).lstrip('0'))
		# Set our desired precision based on the calculations, overriding it
		# with the currency's precision if it's set and is smaller
		precision = zeroes + max_decimals
		if self.precision is not None:
			precision = min(precision, self.precision)
		# Quantize the value to our desired precision, being explicit about 
		# the context to avoid out-of-bounds errors and unexpected default
		# context values. This either rounds the number down to the precision 
		# or adds trailing zeroes, if necessary.
		sign, digits, exponent = amount.quantize(
			decimal.Decimal(f'1e-{precision}'),
			context=decimal.Context(
				prec=decimal.MAX_PREC,
				rounding=decimal.ROUND_HALF_UP,
			)
		).as_tuple()
		# Normalise the digits to an exponent of zero if exponent is positive.
		# E.g. (digits=(1,), exponent=2) becomes (digits=(1,0,0), exponent=0)
		if exponent > 0:
			digits += (0,) * exponent
			exponent = 0
		# Fill in leading zeroes for numbers less than 1 to make logic easier.
		# E.g. (digits(1,), exponent=-2) becomes (digits=(0,0,1), exponent=-2)
		if -exponent + 1 > len(digits):
			digits = (0,) * (-exponent - len(digits) + 1) + digits
		# Use Django's number_format to format the integer part of the number,
		# which will apply the grouping and thousand separators used by the 
		# language active in this request
		if not exponent:
			number = number_format(''.join(map(str, digits)))
		else:
			number = number_format(''.join(map(str, digits[:exponent]))) \
				+ get_format('DECIMAL_SEPARATOR') \
				+ ''.join(map(str, digits[exponent:]))
		# Keep trailing zeroes for fiat currencies
		if not self.fiat:
			number = number.rstrip('0').rstrip('.')
		# Use prefix, if available
		if self.prefix:
			number = f'{self.prefix}{number}'
		else:
			number = f'{self.ticker} {number}'
		# Enclose negative numbers in parentheses
		if sign:
			return f'({number})'
		return number


class Pair(models.Model):
	source = models.ForeignKey('Currency',
		related_name='source_pair',
		on_delete=models.CASCADE,
	)
	target = models.ForeignKey('Currency',
		related_name='target_pair', 
		on_delete=models.CASCADE,
	)
	earliest_data = models.DateTimeField(null=True, blank=True)
	latest_data = models.DateTimeField(null=True, blank=True)
	granularity = models.IntegerField(help_text='in seconds')
	data_source = models.CharField(max_length=256, blank=True)

	def __str__(self):
		return ''.join((
			f'{self.source.get_short_name()}/{self.target.get_short_name()}',
			f', {self.get_granularity_display()}',
			f' (via {self.data_source})' if self.data_source else '',
		))
	
	def get_granularity_display(self):
		if self.granularity < 60 or self.granularity % 60:
			value = self.granularity
			unit = 'second'
		elif self.granularity / 60 < 60 or self.granularity % (60 * 60):
			value = self.granularity // 60
			unit = 'minute'
		elif self.granularity / (60 * 60) < 24 or self.granularity % (60 * 60 * 24):
			value = self.granularity // 60 // 60
			unit = 'hour'
		else:
			value = self.granularity // 60 // 60 // 24
			unit = 'day'
		return f'{value} {unit}{"s" if value > 1 else ""}'

	def update_timespan(self):
		"""
		Update earliest and latest data fields based on the records present
		for this pair in the database, and save.
		"""
		self.earliest_data = MovementData.objects.filter(pair=self)\
			.aggregate(models.Min('timestamp'))['timestamp__min']
		self.latest_data = MovementData.objects.filter(pair=self)\
			.aggregate(models.Max('timestamp'))['timestamp__max']
		self.save()

	def price_at(self, timestamp):
		"""
		Return the price of the target currency in the source currency at
		provided `timestamp`.

		TODO: make this use smoothing or other outlier detection
		TODO: handle missing candles
		TODO: accept argument as to which way to err
		"""
		record = self.records.filter(timestamp__lte=timestamp).order_by('timestamp')[0]
		return (record.high + record.low) / decimal.Decimal(2)


class MovementData(models.Model):
	pair = models.ForeignKey('Pair',
		related_name='records',
		on_delete=models.CASCADE,
	)
	timestamp = models.DateTimeField(unique=True)
	open = models.DecimalField(max_digits=160, decimal_places=32)
	high = models.DecimalField(max_digits=160, decimal_places=32)
	low = models.DecimalField(max_digits=160, decimal_places=32)
	close = models.DecimalField(max_digits=160, decimal_places=32)
	volume = models.DecimalField(max_digits=160, decimal_places=32, null=True)

	class Meta:
		ordering = ['-timestamp',]
		verbose_name_plural = 'movement data'

	def __str__(self):
		return f'{self.pair} @ {self.timestamp}'

