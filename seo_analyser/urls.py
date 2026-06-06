from django.urls import path
from . import views

urlpatterns = [
    path('', views.seo_analyser_page, name='seo_analyser'),
]
