from django.contrib import admin

from .models import Currency, MovementData, Pair


@admin.register(Currency)
class CurencyAdmin(admin.ModelAdmin):
	list_display = ('name', 'ticker', 'fiat',)
	list_filter = ('fiat',)


@admin.register(MovementData)
class MovementDataAdmin(admin.ModelAdmin):
	pass


admin.site.register(Pair)
