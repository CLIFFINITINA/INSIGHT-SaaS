from django.contrib import admin
from .models import Dataset, Dashboard, Chart

admin.site.register(Dataset)
admin.site.register(Dashboard)
admin.site.register(Chart)

admin.site.site_header = "InsightHub 管理后台"
admin.site.site_title = "InsightHub Admin"
admin.site.index_title = "站点管理"
admin.site.site_url = "/"  # 首页跳转到前台首页
