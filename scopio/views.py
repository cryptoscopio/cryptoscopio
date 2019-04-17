import importlib

from django.http import JsonResponse
from django.views.generic import TemplateView

from .models import Record


AVAILABLE_PARSERS = [
	'coinbase',
]

class HomeView(TemplateView):
	template_name = 'home.html'

	def post(self, request, *args, **kwargs):
		response = {'error': '',}
		if request.GET.get('record_type') in AVAILABLE_PARSERS:
			parser = importlib.import_module(
				'scopio.parsers.%s' % request.GET.get('record_type'))
			for record in request.FILES.getlist('records'):
				parser.parse(record)
		else:
			response['error'] = 'Invalid record type specified'
		return JsonResponse(response)
	
	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		context['records'] = Record.objects.all()
		return context
