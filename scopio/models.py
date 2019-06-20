from django.db import models


class RecordGroup(models.Model):
	# Earliest timestamp of contained records, cached here for ease of lookups
	timestamp = models.DateTimeField()
	
	class Meta:
		ordering = ['timestamp']

	def refresh_timestamp(self):
		self.timestamp = self.records.aggregate(models.Min('timestamp'))['timestamp__min']
		self.save()

	def needs_events(self):
		# Assumes the group has been fetched with `prefetch_related` on 
		# records, so it can be queried without hitting the database
		return any(record.needs_event for record in self.records.all())


class Record(models.Model):
	timestamp = models.DateTimeField()
	group = models.ForeignKey('RecordGroup', on_delete=models.CASCADE, related_name='records')
	currency = models.ForeignKey('currencio.Currency', on_delete=models.CASCADE)
	amount = models.DecimalField(max_digits=160, decimal_places=32)
	# Using a separate field instead of relying on the sign of the amount 
	# because zero amounts are possible, and negative zero cannot be stored
	outgoing = models.BooleanField()
	platform = models.CharField(max_length=64)
	transaction = models.CharField(max_length=1024)
	to_address = models.CharField(max_length=1024)
	from_address = models.CharField(max_length=1024)
	identifier = models.CharField(max_length=1024)
	is_fee = models.BooleanField(default=False)
	needs_event = models.BooleanField(default=True)

	class Meta:
		ordering = ['timestamp']

	def __str__(self):
		amount = self.currency.format_amount(self.amount if not self.outgoing else -self.amount)
		if self.is_fee:
			action = 'Paid fee of'
		elif self.platform and not self.transaction:
			if self.currency.fiat:
				action = 'Spent' if self.outgoing else 'Credited'
			else:
				action = 'Sold' if self.outgoing else 'Purchased'
		else:
			action = 'Sent' if self.outgoing else 'Received'
		return f'{action} {amount}'


class Event(models.Model):
	DISPOSAL = 0
	ACQUISITION = 1
	DISPOSAL_FEE = 2
	FIAT_FEE = 3
	
	TYPE_CHOICES = (
		(DISPOSAL, 'Disposal'),
		(ACQUISITION, 'Acquisition'),
		(DISPOSAL_FEE, 'Disposal (fee)'),
		(FIAT_FEE, 'Fiat fee'),
	)

	type = models.IntegerField(choices=TYPE_CHOICES)
	record = models.OneToOneField('Record', on_delete=models.CASCADE, related_name='event')
	currency = models.ForeignKey('currencio.Currency', on_delete=models.CASCADE)
	amount = models.DecimalField(max_digits=160, decimal_places=32)
	price = models.DecimalField(max_digits=160, decimal_places=32, null=True)

	class Meta:
		ordering = ['record__timestamp']

	def __str__(self):
		# TODO: replace this with a sane method of getting the price currency
		from currencio.models import Currency
		user_currency = Currency.objects.get(ticker='AUD', fiat=True)
		return ''.join((
			f'{self.get_type_display()}: {self.currency.format_amount(self.amount)}',
			f' at {user_currency.format_amount(self.price)}' if self.price is not None else '',
		))

	def get_style_class(self):
		if self.type in [Event.DISPOSAL, Event.DISPOSAL_FEE]:
			return 'event-disposal'
		if self.type in [Event.ACQUISITION]:
			return 'event-acquisition'
		return 'event-neutral'

	def get_amount_display(self):
		if self.type in [Event.FIAT_FEE]:
			return f'{self.amount:.2f}'
		return f'{str(self.amount).rstrip("0")}'
