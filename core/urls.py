
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/generate-blog/', views.generate_blog, name='generate_blog'),
]