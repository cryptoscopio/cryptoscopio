from django.db import models


class Record(models.Model):
	id = models.CharField(max_length=1024, primary_key=True)
	timestamp = models.DateTimeField()
	amount = models.DecimalField(max_digits=160, decimal_places=32)
	currency = models.ForeignKey('currencio.Currency', on_delete=models.CASCADE)
	tx_hash = models.CharField(max_length=1024, blank=True)
	price = models.DecimalField(
		max_digits=160, decimal_places=32,
		null=True, blank=True,
	)
	fiat = models.ForeignKey('currencio.Currency',
		on_delete=models.CASCADE,
		related_name='fiat_record',
		null=True, blank=True,
	)
	match = models.OneToOneField('Record',
		on_delete=models.SET_NULL,
		null=True, blank=True,
	)
	events = models.ManyToManyField('Event')

	class Meta:
		ordering = ['timestamp']

	def __str__(self):
		if self.price:
			action = 'Purchased' if self.amount >= 0 else 'Sold'
			return f'{action} {self.currency.format_amount(self.amount)} for {self.fiat.format_amount(self.amount * self.price)}'
		action = 'Incoming' if self.amount >= 0 else 'Outgoing'
		return f'{action} transfer of {self.currency.format_amount(self.amount)}'

	def platform(self):
		return self.id.split()[0]


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
	timestamp = models.DateTimeField()
	currency = models.ForeignKey('currencio.Currency', on_delete=models.CASCADE)
	amount = models.DecimalField(max_digits=160, decimal_places=32)
	price = models.DecimalField(max_digits=160, decimal_places=32, null=True)

	class Meta:
		ordering = ['timestamp']

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
