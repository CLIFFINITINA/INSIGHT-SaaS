from django.urls import path, include

from . import views
from .views import dataset_ai_summary_api, dashboard_reorder_charts, home_view

urlpatterns = [
    path('', home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('upload/', views.upload_view, name='upload'),
    path('datasets/', views.datasets_view, name='datasets'),
    path('datasets/<int:dataset_id>/', views.dataset_detail_view, name='dataset_detail'),
    path('datasets/<int:dataset_id>/api/', views.dataset_detail_api, name='dataset_detail_api'),
    path('datasets/<int:dataset_id>/ai_summary/', dataset_ai_summary_api, name='dataset_ai_summary_api'),
    path('logout/', views.logout_view, name='logout'),
    # path('accounts/', include('django.contrib.auth.urls')),  # 已禁用，避免logout路由冲突
    
    # Dashboard URLs
    path('dashboards/', views.dashboard_list, name='dashboard_list'),
    path('dashboard/create/', views.create_dashboard, name='create_dashboard'),
    path('dashboard/<int:dashboard_id>/', views.dashboard_detail, name='dashboard_detail'),
    path('dashboard/<int:dashboard_id>/edit/', views.edit_dashboard, name='edit_dashboard'),
    path('dashboard/<int:dashboard_id>/delete/', views.delete_dashboard, name='delete_dashboard'),
    path('dashboard/<int:dashboard_id>/reorder_charts/', dashboard_reorder_charts, name='dashboard_reorder_charts'),
    
    # Chart URLs
    path('dashboard/<int:dashboard_id>/chart/create/', views.create_chart, name='create_chart'),
    path('chart/<int:chart_id>/edit/', views.edit_chart, name='edit_chart'),
    path('chart/<int:chart_id>/delete/', views.delete_chart, name='delete_chart'),
    
    # Public dashboard URL
    path('public/dashboard/<int:dashboard_id>/', views.public_dashboard, name='public_dashboard'),
    path('datasets/batch_delete/', views.batch_delete_datasets, name='batch_delete_datasets'),
    path('datasets/rename/', views.rename_dataset, name='rename_dataset'),
    path('datasets/<int:dataset_id>/save_chart_config/', views.save_user_chart_config, name='save_user_chart_config'),
    path('QR/dataset/<int:dataset_id>/', views.qr_dataset, name='qr_dataset'),
    path('QR/dashboard/<int:dashboard_id>/', views.qr_dashboard, name='qr_dashboard'),
    path('QR/dataset/<int:dataset_id>/display/', views.qr_dataset_display, name='qr_dataset_display'),
    path('QR/dashboard/<int:dashboard_id>/display/', views.qr_dashboard_display, name='qr_dashboard_display'),
]
