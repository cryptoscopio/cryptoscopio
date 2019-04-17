from django.db import models


class Record(models.Model):
	id = models.CharField(max_length=1024, primary_key=True)
	timestamp = models.DateTimeField()
	amount = models.DecimalField(max_digits=160, decimal_places=32)
	currency = models.CharField(max_length=24) # TODO: make into FK
	tx_hash = models.CharField(max_length=1024, blank=True)
	price = models.DecimalField(blank=True, null=True, max_digits=160, decimal_places=32)
	fiat = models.CharField(max_length=24, blank=True) # TODO: make into FK
	match = models.OneToOneField('Record', on_delete=models.SET_NULL, null=True, blank=True)
	events = models.ManyToManyField('Event')

	class Meta:
		ordering = ['timestamp']

	def __str__(self):
		if self.price:
			action = 'Purchased' if self.amount >= 0 else 'Sold'
			return f'{action} {self.currency} {str(self.amount).rstrip("0")} for {self.fiat} {self.amount * self.price:.2f}'
		action = 'Incoming' if self.amount >= 0 else 'Outgoing'
		return f'{action} transfer of {self.currency} {str(self.amount).rstrip("0")}'

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
	currency = models.CharField(max_length=24) # TODO: make into FK
	amount = models.DecimalField(max_digits=160, decimal_places=32)
	price = models.DecimalField(max_digits=160, decimal_places=32, null=True)

	class Meta:
		ordering = ['timestamp']

	def __str__(self):
		return f'{self.get_type_display()}: {self.currency} {self.amount}'

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
