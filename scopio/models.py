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

