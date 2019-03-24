import codecs
import io


def wrap_uploaded_file(file_):
	for chunk in file_.chunks():
		for line in codecs.getreader('utf-8')(io.BytesIO(chunk)):
			yield line

