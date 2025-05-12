from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),  # 添加语言切换的 URL pattern
    path('', include('core.urls')),  # ✅ 非常关键：加载 core 应用的 urls.py
]
