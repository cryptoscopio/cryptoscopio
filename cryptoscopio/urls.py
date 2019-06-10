from django.contrib import admin
from django.urls import path

from scopio import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.HomeView.as_view(), name='home'),
	path('parse-address/', views.ParseAddressView.as_view(), name='parse-address'),
	path('upload-records/', views.UploadRecordsView.as_view(), name='upload-records'),
]

