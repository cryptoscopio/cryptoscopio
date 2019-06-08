from django.http import JsonResponse
from django.views.generic import TemplateView

from .models import Record
from .parsers import parsers
from .utils import wrap_uploaded_file


class HomeView(TemplateView):
	template_name = 'home.html'

	def post(self, request, *args, **kwargs):
		response = {'error': '',}
		try:
			parser = parsers[request.GET.get('record_type')]
			for record in request.FILES.getlist('records'):
				parser.parse_file(wrap_uploaded_file(record))
		except KeyError:
			response['error'] = 'Invalid record type specified'
		return JsonResponse(response)
	
	def get_context_data(self, *args, **kwargs):
		context = super().get_context_data(*args, **kwargs)
		context.update({
			'parsers': parsers,
			'records': Record.objects.all(),
		})
		return context
