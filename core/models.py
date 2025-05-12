from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import os

class Dataset(models.Model):
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='datasets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    schema = models.JSONField(null=True, blank=True)
    ai_suggestion = models.JSONField(null=True, blank=True)  # 缓存AI推荐结果
    ai_summary = models.TextField(null=True, blank=True)  # 缓存AI英文归纳分析

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)

# 恢复Dashboard模型
class Dashboard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Chart(models.Model):
    CHART_TYPES = [
        ('bar', 'Bar'),
        ('line', 'Line'),
        ('pie', 'Pie'),
        # ('histogram', 'Histogram'),
        # ('box', 'Box'),
    ]
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default='')
    chart_type = models.CharField(max_length=50, choices=CHART_TYPES)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    x_column = models.CharField(max_length=100)
    y_column = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    order = models.PositiveIntegerField(default=0)  # 图表排序

    def __str__(self):
        return f"{self.name} - {self.get_chart_type_display()}"

class UserDatasetChartConfig(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    chart_type = models.CharField(max_length=50)
    x_field = models.CharField(max_length=100)
    y_field = models.CharField(max_length=100)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'dataset')
