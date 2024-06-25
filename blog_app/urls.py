from django.urls import path
from .views import post_views, upload_views, detail_views

app_name = 'blog_app'

urlpatterns = [
    path("", post_views.post_all, name='post_list'),
    path("upload/", upload_views.post_upload, name='post_upload'),
    path("search/", post_views.search, name='search'),
    path('<int:pk>/', detail_views.post_detail, name='post_detail'),
    path('<int:pk>/like/', detail_views.post_like, name='post_like'),
    path('new/', detail_views.post_create, name='post_create'),
    path('<int:post_pk>/comment/new/', detail_views.comment_create, name='comment_create'),
    path('<int:pk>/delete/', detail_views.post_delete, name='post_delete'),
    path('<int:pk>/edit/', detail_views.post_edit, name='post_edit'),
    path('<int:post_pk>/comment/<int:comment_pk>/delete/', detail_views.comment_delete, name='comment_delete'),
]