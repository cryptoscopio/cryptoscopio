from django import forms
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.views.generic.edit import FormView

from currencio.models import Currency

from .explorers import explorers
from .models import RecordGroup
from .parsers import parsers
from .utils import wrap_uploaded_file


class ParseAddressForm(forms.Form):
	blockchain = forms.ChoiceField(
		choices=((name, explorer.DISPLAY_NAME) for name, explorer in explorers.items()),
		label='Cryptocurrency',
	)
	addresses = forms.CharField(
		widget=forms.Textarea,
		label='Addresses (separate multiple addresses across new lines)',
	)

class ParseAddressView(FormView):
	form_class = ParseAddressForm
	
	def get(self, *args, **kwargs):
		return HttpResponseNotAllowed(['POST'])

	def post(self, request, *args, **kwargs):
		form = self.get_form()
		if form.is_valid():
			results = {'title': 'Addresses parsed', 'messages': []}
			explorer = explorers[form.cleaned_data['blockchain']]
			# Separate multiple addresses and discard whitespace
			addresses = filter(bool, form.cleaned_data['addresses'].split())
			for address in addresses:
				error = explorer.validate_address(address)
				if error:
					results['messages'] += [{
						'type': 'error',
						'text': f'Failed to parse address {address}',
						'notes': [{
							'type': 'info',
							'text': error,
						}]
					}]
					continue
				# TODO: Wrap in transaction control
				explorer.parse_address(address)
		else:
			# Since we know what the possible errors are, show a more 
			# user-friendly message instead of what's in `form.errors`.
			results = {
				'title': 'Error parsing addresses',
				'messages': [{
					'type': 'error',
					'text': 'Invalid cryptocurrency selected or no addresses provided',
				}]
			}
		request.session['results'] = results
		return redirect('home')


class UploadRecordsForm(forms.Form):
	platform = forms.ChoiceField(
		choices=((name, parser.DISPLAY_NAME) for name, parser in parsers.items()),
	)
	records = forms.FileField(
		widget=forms.ClearableFileInput(attrs={'multiple': True, 'accept': '.csv'}),
		label='',
	)

class UploadRecordsView(FormView):
	form_class = UploadRecordsForm
	
	def get(self, *args, **kwargs):
		return HttpResponseNotAllowed(['POST'])

	def post(self, request, *args, **kwargs):
		form = self.get_form()
		if form.is_valid():
			results = {'title': 'Records parsed', 'messages': []}
			parsed_files = 0
			parser = parsers[form.cleaned_data['platform']]
			for record in request.FILES.getlist('records'):
				try:
					# Parse the file using the selected platform parser
					# TODO: Wrap in transaction control
					parsed, skipped, failed = \
						parser.parse_file(wrap_uploaded_file(record))
					# Construct message to show the user about the outcome
					message = {
						'type': 'info',
						'text': f'Parsed file {record.name}',
						'notes': [],
					}
					if parsed:
						message['notes'] += [{
							'type': 'success',
							'text': f'Parsed {parsed} new records',
						}]
					if skipped:
						message['notes'] += [{
							'type': 'warning',
							'text': f'Skipped {skipped} records that were already parsed',
						}]
					if failed:
						message['notes'] += [{
							'type': 'error',
							'text': f'Failed to parse {skipped} unrecognised records',
						}]
				# TODO: More robust error dectection
				except ValueError:
					message = {
						'type': 'error',
						'text': f'Failed to parse file {record.name}: unrecognised format',
					}
				results['messages'] += [message]
				# Write results to session, so that in case of failure or 
				# timeout, the user is told what was parsed so far
				request.session['results'] = results
		else:
			# Since we know what the possible errors are, show a more 
			# user-friendly message instead of what's in `form.errors`.
			results = {
				'title': 'Error parsing records',
				'messages': [{
					'type': 'error',
					'text': 'Invalid platform selected or no files selected for upload',
				}]
			}
			request.session['results'] = results
		return redirect('home')


class HomeView(TemplateView):
	template_name = 'home.html'
	
	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		context.update({
			'currencies': Currency.objects.filter(fiat=True),
			'groups': RecordGroup.objects.prefetch_related(
				'records', 'records__event', 'records__currency'
			),
			'results': self.request.session.pop('results', {}),
			'additional': self.request.session.pop('additional', {}),
			'parse_address_form': ParseAddressForm(),
			'upload_records_form': UploadRecordsForm(),
		})
		return context

