from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('debug-env/', views.debug_env, name='debug_env'),  # ← add this
    path('api/generate-blog/', views.generate_blog, name='generate_blog'),
    path('api/download-pdf/', views.download_pdf, name='download_pdf'),
    path('api/seo-analyze/', views.seo_analyze, name='seo_analyze'),
]
