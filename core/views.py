from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .models import Dataset, Dashboard, Chart, UserDatasetChartConfig
from .forms import RegisterForm, DatasetUploadForm
from .services.csv_utils import extract_schema, get_numeric_columns, load_csv
from .services.chart_utils import prepare_chart_data
from .services.ai_utils import recommend_chart_and_fields, summarize_csv_with_openai
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import os
from django.db.models import Q
import qrcode
from io import BytesIO
from django.http import HttpResponse
from django.utils.html import escape
import pandas as pd

# 登录页为默认入口
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_list')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard_list')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

# 注册页
def register_view(request):
    if request.user.is_authenticated:
        return redirect('upload')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('upload')
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})

# 上传页
@login_required
def upload_view(request):
    if request.method == 'POST':
        form = DatasetUploadForm(request.POST, request.FILES)
        files = request.FILES.getlist('file')
        created = 0
        for f in files:
            dataset = Dataset(
                name=os.path.splitext(f.name)[0],
                file=f,
                user=request.user
            )
            # 自动提取表结构
            df = load_csv(f)
            dataset.schema = extract_schema(df)
            # --- 新增：上传后自动AI分析并缓存 ---
            schema = dataset.schema
            sample_rows = df.head(5).to_dict(orient='records')
            ai_result = recommend_chart_and_fields(schema, sample_rows)
            dataset.ai_suggestion = ai_result
            ai_summary = summarize_csv_with_openai(schema, sample_rows)
            dataset.ai_summary = ai_summary
            # --- END ---
            dataset.save()
            created += 1
        if created:
            return redirect('datasets')
        else:
            return redirect('datasets')
    else:
        form = DatasetUploadForm()
    return render(request, 'core/upload.html', {'form': form})

# 数据集列表
@login_required
def datasets_view(request):
    if request.user.is_superuser or request.user.is_staff:
        datasets = Dataset.objects.all().order_by('-uploaded_at')
    else:
        datasets = Dataset.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'core/datasets.html', {'datasets': datasets})

# 数据集详情+图表
@login_required
def dataset_detail_view(request, dataset_id):
    dataset = get_object_or_404(Dataset, pk=dataset_id)
    df = load_csv(dataset.file.path)
    schema = extract_schema(df)
    sample_rows = df.head(5).to_dict(orient='records')
    # 优先读取用户自定义配置
    user_config = None
    try:
        user_config = UserDatasetChartConfig.objects.filter(user=request.user, dataset=dataset).first()
    except Exception:
        user_config = None
    ai_result = dataset.ai_suggestion
    if not ai_result:
        ai_result = recommend_chart_and_fields(schema, sample_rows)
        dataset.ai_suggestion = ai_result
        dataset.save(update_fields=["ai_suggestion"])
    ai_reason = ai_result.get("reason") or ai_result.get("raw_reply") if ai_result else None
    # chart_type/x/y优先用用户配置，否则用AI推荐
    if user_config:
        chart_type = user_config.chart_type
        x_field = user_config.x_field
        y_field = user_config.y_field
    else:
        chart_type = ai_result.get('chart_type', 'bar') if ai_result else 'bar'
        x_field = ai_result.get('x_field')
        y_field = ai_result.get('y_field')
    # 字段有效性校验
    if not (x_field in df.columns and y_field in df.columns):
        numeric_cols = get_numeric_columns(df)
        if len(numeric_cols) >= 2:
            x_field, y_field = numeric_cols[:2]
        else:
            x_field = y_field = None
    x = df[x_field].tolist() if x_field in df.columns else []
    y = df[y_field].tolist() if y_field in df.columns else []
    chart_data = None
    chart_error = None
    if x_field and y_field:
        chart_data = prepare_chart_data(df, x_field, y_field, chart_type)
    else:
        chart_error = '数据集缺少足够的数值型字段，无法自动生成图表。'
    return render(request, 'core/dataset_detail.html', {
        'dataset': dataset,
        'chart_data': chart_data,
        'chart_error': chart_error,
        'ai_reason': ai_reason,
        'x_field': x_field,
        'y_field': y_field,
        'chart_type': chart_type,
        'all_fields': list(df.columns),
    })

@login_required
def dataset_detail_api(request, dataset_id):
    try:
        dataset = get_object_or_404(Dataset, pk=dataset_id)
        df = load_csv(dataset.file.path)
        
        # 获取请求参数
        req_chart_type = request.GET.get('chart_type')
        req_x = request.GET.get('x_field')
        req_y = request.GET.get('y_field')
        
        # 验证参数
        if not req_chart_type or not req_x or not req_y:
            return JsonResponse({
                'error': '缺少必要的参数',
                'chart_error': '请提供图表类型、X轴和Y轴字段'
            })
        
        # 获取AI推荐
        ai_result = dataset.ai_suggestion
        if not ai_result:
            try:
                schema = extract_schema(df)
                sample_rows = df.head(5).to_dict(orient='records')
                ai_result = recommend_chart_and_fields(schema, sample_rows)
                dataset.ai_suggestion = ai_result
                dataset.save(update_fields=["ai_suggestion"])
            except Exception as e:
                print(f"AI推荐失败: {e}")
                ai_result = None
        
        # 准备图表数据
        try:
            chart_data = prepare_chart_data(df, req_x, req_y, req_chart_type)
            if 'error' in chart_data:
                return JsonResponse({
                    'chart_error': chart_data['error'],
                    'ai_reason': ai_result.get("reason") if ai_result else None,
                    'ai_chart_type': ai_result.get('chart_type') if ai_result else None,
                    'ai_x_field': ai_result.get('x_field') if ai_result else None,
                    'ai_y_field': ai_result.get('y_field') if ai_result else None,
                    'all_fields': list(df.columns)
                })
        except Exception as e:
            return JsonResponse({
                'chart_error': f'处理图表数据时出错: {str(e)}',
                'ai_reason': ai_result.get("reason") if ai_result else None,
                'ai_chart_type': ai_result.get('chart_type') if ai_result else None,
                'ai_x_field': ai_result.get('x_field') if ai_result else None,
                'ai_y_field': ai_result.get('y_field') if ai_result else None,
                'all_fields': list(df.columns)
            })
        
        return JsonResponse({
            'chart_data': chart_data,
            'ai_reason': ai_result.get("reason") if ai_result else None,
            'ai_chart_type': ai_result.get('chart_type') if ai_result else None,
            'ai_x_field': ai_result.get('x_field') if ai_result else None,
            'ai_y_field': ai_result.get('y_field') if ai_result else None,
            'all_fields': list(df.columns)
        })
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({
            'chart_error': f'服务器错误: {str(e)}',
            'ai_reason': None,
            'chart_data': None
        })

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dataset_ai_summary_api(request, dataset_id):
    """
    返回AI英文归纳summary，优先读取和写入Dataset.ai_summary字段。
    只有为空时才请求OpenAI并写入数据库。
    """
    dataset = get_object_or_404(Dataset, pk=dataset_id)
    summary = dataset.ai_summary
    if not summary:
        df = load_csv(dataset.file.path)
        schema = extract_schema(df)
        sample_rows = df.head(5).to_dict(orient='records')
        summary = summarize_csv_with_openai(schema, sample_rows)
        dataset.ai_summary = summary
        dataset.save(update_fields=["ai_summary"])
    return JsonResponse({"summary": summary})

@login_required
def dashboard_reorder_charts(request, dashboard_id):
    if request.method == 'POST':
        dashboard = get_object_or_404(Dashboard, id=dashboard_id, user=request.user)
        data = json.loads(request.body.decode())
        ids = data.get('order', [])
        for idx, cid in enumerate(ids):
            try:
                chart = Chart.objects.get(id=cid, dashboard=dashboard)
                chart.order = idx
                chart.save(update_fields=["order"])
            except Exception as e:
                print(f"排序更新失败: {e}")
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=400)

@require_POST
@login_required
def batch_delete_datasets(request):
    ids = request.POST.getlist('dataset_ids')
    if ids:
        datasets = Dataset.objects.filter(id__in=ids, user=request.user)
        for dataset in datasets:
            dataset.delete()  # 这会触发我们自定义的delete方法
    return redirect('datasets')

# 仪表盘列表
@login_required
def dashboard_list(request):
    from django.db.models import Q
    if request.user.is_superuser or request.user.is_staff:
        dashboards = Dashboard.objects.all().order_by('-created_at')
    else:
        dashboards = Dashboard.objects.filter(
            Q(user=request.user) | Q(is_public=True)
        ).order_by('-created_at')
    return render(request, 'core/dashboard_list.html', {'dashboards': dashboards})

# 创建仪表盘
@login_required
def create_dashboard(request):
    datasets = Dataset.objects.filter(user=request.user)
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        is_public = request.POST.get('is_public') == 'on'
        dataset_ids = request.POST.getlist('datasets')
        dashboard = Dashboard.objects.create(user=request.user, name=name, description=description, is_public=is_public)
        # 为每个选中的数据集自动生成一个图表（AI推荐配置）
        for ds_id in dataset_ids:
            try:
                dataset = Dataset.objects.get(id=ds_id)
                ai = dataset.ai_suggestion or {}
                chart_type = ai.get('chart_type', 'bar')
                x_field = ai.get('x_field')
                y_field = ai.get('y_field')
                # 如果AI推荐无效，自动选前两个字段
                if not (x_field and y_field and x_field in dataset.schema and y_field in dataset.schema):
                    cols = list(dataset.schema.keys()) if dataset.schema else []
                    if len(cols) >= 2:
                        x_field, y_field = cols[:2]
                    else:
                        x_field = y_field = ''
                Chart.objects.create(
                    dashboard=dashboard,
                    name=f"{dataset.name} Visualization",
                    chart_type=chart_type,
                    dataset=dataset,
                    x_column=x_field or '',
                    y_column=y_field or '',
                    description=f"AI recommended, editable later"
                )
            except Exception as e:
                print(f"创建图表失败: {e}")
        return redirect('dashboard_detail', dashboard_id=dashboard.id)
    return render(request, 'core/create_dashboard.html', {'datasets': datasets})

# 编辑仪表盘
@login_required
def edit_dashboard(request, dashboard_id):
    if request.user.is_superuser or request.user.is_staff:
        dashboard = get_object_or_404(Dashboard, id=dashboard_id)
    else:
        dashboard = Dashboard.objects.filter(id=dashboard_id, user=request.user).first()
        if dashboard is None:
            return HttpResponseForbidden('You do not have permission to edit this dashboard.')
    if request.method == 'POST':
        dashboard.name = request.POST.get('name', dashboard.name)
        dashboard.description = request.POST.get('description', dashboard.description)
        dashboard.is_public = request.POST.get('is_public') == 'on' if 'is_public' in request.POST else dashboard.is_public
        dashboard.save()
        return redirect('dashboard_detail', dashboard_id=dashboard.id)
    return render(request, 'core/edit_dashboard.html', {'dashboard': dashboard})

# 删除仪表盘
@login_required
def delete_dashboard(request, dashboard_id):
    if request.user.is_superuser or request.user.is_staff:
        dashboard = get_object_or_404(Dashboard, id=dashboard_id)
    else:
        dashboard = Dashboard.objects.filter(id=dashboard_id, user=request.user).first()
        if dashboard is None:
            return HttpResponseForbidden('You do not have permission to delete this dashboard.')
    dashboard.delete()
    return redirect('dashboard_list')

# 仪表盘详情
@login_required
def dashboard_detail(request, dashboard_id):
    if request.user.is_superuser or request.user.is_staff:
        dashboard = get_object_or_404(Dashboard, id=dashboard_id)
    else:
        dashboard = get_object_or_404(
            Dashboard.objects.filter(
                Q(id=dashboard_id) & (Q(user=request.user) | Q(is_public=True))
            )
        )
    charts = Chart.objects.filter(dashboard=dashboard).order_by('order', 'id')
    return render(request, 'core/dashboard_detail.html', {'dashboard': dashboard, 'charts': charts})

# 创建图表
@login_required
def create_chart(request, dashboard_id):
    dashboard = get_object_or_404(Dashboard, id=dashboard_id, user=request.user)
    datasets = Dataset.objects.filter(user=request.user)
    # 新增：为每个数据集准备推荐的x/y字段
    dataset_recommend = {}
    for ds in datasets:
        ai = ds.ai_suggestion or {}
        x_field = ai.get('x_field')
        y_field = ai.get('y_field')
        # 如果AI推荐无效，自动选前两个字段
        if not (x_field and y_field and ds.schema and x_field in ds.schema and y_field in ds.schema):
            cols = list(ds.schema.keys()) if ds.schema else []
            if len(cols) >= 2:
                x_field, y_field = cols[:2]
            else:
                x_field = y_field = ''
        dataset_recommend[ds.id] = {'x': x_field, 'y': y_field}

    ai_x = ai_y = None
    all_fields = []
    selected_dataset_id = None
    if request.method == 'POST':
        name = request.POST.get('name')
        chart_type = request.POST.get('chart_type')
        dataset_id = request.POST.get('dataset')
        x_column = request.POST.get('x_column')
        y_column = request.POST.get('y_column')
        description = request.POST.get('description')
        dataset = get_object_or_404(Dataset, id=dataset_id)
        # 如果name为空，则用数据集名称兜底
        if not name or not name.strip():
            name = dataset.name
        Chart.objects.create(
            dashboard=dashboard,
            name=name,
            chart_type=chart_type,
            dataset=dataset,
            x_column=x_column,
            y_column=y_column,
            description=description
        )
        return redirect('dashboard_detail', dashboard_id=dashboard_id)
    else:
        # GET 请求，准备推荐字段
        dataset_id = request.GET.get('dataset')
        if not dataset_id and datasets:
            dataset_id = str(datasets[0].id)
        if dataset_id:
            try:
                dataset_id_int = int(dataset_id)
                selected_dataset_id = dataset_id_int
                rec = dataset_recommend.get(dataset_id_int)
                if rec:
                    ai_x = rec.get('x')
                    ai_y = rec.get('y')
                # 获取所有字段
                ds = next((d for d in datasets if d.id == dataset_id_int), None)
                if ds and ds.schema:
                    all_fields = list(ds.schema.keys())
            except Exception:
                pass
    return render(request, 'core/create_chart.html', {
        'dashboard': dashboard,
        'datasets': datasets,
        'dataset_recommend': dataset_recommend,
        'ai_x': ai_x,
        'ai_y': ai_y,
        'all_fields': all_fields,
        'selected_dataset_id': selected_dataset_id,
    })

# 编辑图表
@login_required
def edit_chart(request, chart_id):
    chart = get_object_or_404(Chart, id=chart_id, dashboard__user=request.user)
    datasets = Dataset.objects.filter(user=request.user)
    ai_type = ai_x = ai_y = None
    ai_fields = []
    if chart.dataset and chart.dataset.ai_suggestion:
        ai_type = chart.dataset.ai_suggestion.get('chart_type')
        ai_x = chart.dataset.ai_suggestion.get('x_field')
        ai_y = chart.dataset.ai_suggestion.get('y_field')
    df = load_csv(chart.dataset.file.path)
    all_fields = list(df.columns)
    if request.method == 'POST':
        chart.name = request.POST.get('name')
        chart.chart_type = request.POST.get('chart_type')
        dataset_id = request.POST.get('dataset')
        chart.x_column = request.POST.get('x_column')
        chart.y_column = request.POST.get('y_column')
        chart.description = request.POST.get('description')
        chart.dataset = get_object_or_404(Dataset, id=dataset_id)
        chart.save()
        return redirect('dashboard_detail', dashboard_id=chart.dashboard.id)
    return render(request, 'core/edit_chart.html', {
        'chart': chart,
        'datasets': datasets,
        'ai_type': ai_type,
        'ai_x': ai_x,
        'ai_y': ai_y,
        'all_fields': all_fields,
    })

# 删除图表
@login_required
def delete_chart(request, chart_id):
    chart = get_object_or_404(Chart, id=chart_id, dashboard__user=request.user)
    dashboard_id = chart.dashboard.id
    chart.delete()
    return redirect('dashboard_detail', dashboard_id=dashboard_id)

# 公开仪表盘
def public_dashboard(request, dashboard_id):
    dashboard = get_object_or_404(Dashboard, id=dashboard_id, is_public=True)
    charts = Chart.objects.filter(dashboard=dashboard)
    return render(request, 'core/public_dashboard.html', {'dashboard': dashboard, 'charts': charts})

@require_POST
@login_required
def rename_dataset(request):
    try:
        data = json.loads(request.body.decode())
        dataset_id = data.get('id')
        new_name = data.get('name')
        if not dataset_id or not new_name:
            return JsonResponse({'success': False, 'error': '参数缺失'})
        dataset = Dataset.objects.get(id=dataset_id, user=request.user)
        dataset.name = new_name
        dataset.save(update_fields=['name'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# 新增：保存用户自定义图表参数API
@login_required
@require_POST
def save_user_chart_config(request, dataset_id):
    dataset = get_object_or_404(Dataset, pk=dataset_id)
    data = json.loads(request.body.decode())
    chart_type = data.get('chart_type')
    x_field = data.get('x_field')
    y_field = data.get('y_field')
    if not (chart_type and x_field and y_field):
        return JsonResponse({'success': False, 'error': '参数不完整'})
    obj, created = UserDatasetChartConfig.objects.update_or_create(
        user=request.user, dataset=dataset,
        defaults={
            'chart_type': chart_type,
            'x_field': x_field,
            'y_field': y_field
        }
    )
    return JsonResponse({'success': True})

# 公开二维码页面：数据集
@csrf_exempt
def qr_dataset(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id)
    url = request.build_absolute_uri(f'/QR/dataset/{dataset_id}/display/')
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format='PNG')
    qr_img_data = buf.getvalue()
    import base64
    qr_img_base64 = 'data:image/png;base64,' + base64.b64encode(qr_img_data).decode()
    return render(request, 'core/qr_dataset.html', {
        'dataset': dataset,
        'qr_img_base64': qr_img_base64,
        'url': url,
    })

# 公开二维码页面：仪表盘
@csrf_exempt
def qr_dashboard(request, dashboard_id):
    dashboard = get_object_or_404(Dashboard, id=dashboard_id)
    url = request.build_absolute_uri(f'/QR/dashboard/{dashboard_id}/display/')
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format='PNG')
    qr_img_data = buf.getvalue()
    import base64
    qr_img_base64 = 'data:image/png;base64,' + base64.b64encode(qr_img_data).decode()
    return render(request, 'core/qr_dashboard.html', {
        'dashboard': dashboard,
        'qr_img_base64': qr_img_base64,
        'url': url,
    })

# 公开展示页面：数据集
@csrf_exempt
def qr_dataset_display(request, dataset_id):
    dataset = get_object_or_404(Dataset, id=dataset_id)
    # 读取前5行数据
    sample_rows = []
    columns = []
    chart_data = None
    chart_type = None
    x_field = None
    y_field = None
    chart_error = None
    if dataset.file and hasattr(dataset.file, 'path'):
        try:
            df = pd.read_csv(dataset.file.path)
            sample_rows = df.head(5).to_dict(orient='records')
            columns = list(df.columns)
            # 图表推荐逻辑
            ai_result = getattr(dataset, 'ai_suggestion', None)
            if not ai_result:
                from .services.csv_utils import extract_schema
                from .services.ai_utils import recommend_chart_and_fields
                schema = extract_schema(df)
                ai_result = recommend_chart_and_fields(schema, sample_rows)
                dataset.ai_suggestion = ai_result
                dataset.save(update_fields=["ai_suggestion"])
            chart_type = ai_result.get('chart_type', 'bar') if ai_result else 'bar'
            x_field = ai_result.get('x_field')
            y_field = ai_result.get('y_field')
            # 字段有效性校验
            if not (x_field in df.columns and y_field in df.columns):
                from .services.csv_utils import get_numeric_columns
                numeric_cols = get_numeric_columns(df)
                if len(numeric_cols) >= 2:
                    x_field, y_field = numeric_cols[:2]
                else:
                    x_field = y_field = None
            if x_field and y_field:
                from .services.chart_utils import prepare_chart_data
                chart_data = prepare_chart_data(df, x_field, y_field, chart_type)
                if 'error' in chart_data:
                    chart_error = chart_data['error']
            else:
                chart_error = '数据集缺少足够的数值型字段，无法自动生成图表。'
        except Exception as e:
            sample_rows = []
            columns = []
            chart_error = f'读取数据或生成图表时出错: {str(e)}'
    return render(request, 'core/qr_dataset_display.html', {
        'dataset': dataset,
        'sample_rows': sample_rows,
        'columns': columns,
        'chart_data': chart_data,
        'chart_type': chart_type,
        'x_field': x_field,
        'y_field': y_field,
        'chart_error': chart_error,
    })

# 公开展示页面：仪表盘
@csrf_exempt
def qr_dashboard_display(request, dashboard_id):
    dashboard = get_object_or_404(Dashboard, id=dashboard_id)
    charts = Chart.objects.filter(dashboard=dashboard).order_by('order', 'id')
    return render(request, 'core/qr_dashboard_display.html', {'dashboard': dashboard, 'charts': charts})

def home_view(request):
    return render(request, 'core/home.html')
