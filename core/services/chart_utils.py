import json
import numpy as np
import pandas as pd

def prepare_chart_data(df, x_field, y_field, chart_type='bar'):
    try:
        # 验证输入数据
        if not isinstance(df, pd.DataFrame):
            return {'error': '无效的数据格式'}
        
        if x_field not in df.columns:
            return {'error': f'X轴字段 "{x_field}" 不存在'}
        
        if y_field not in df.columns:
            return {'error': f'Y轴字段 "{y_field}" 不存在'}
        
        # 获取数据
        x = df[x_field].astype(str).tolist()
        y = df[y_field].tolist()
        
        # 验证数据
        if not x or not y:
            return {'error': '数据为空'}
        
        if len(x) != len(y):
            return {'error': 'X轴和Y轴数据长度不匹配'}
        
        # 过滤空值，保证 x/y 对齐且 y 为数值
        filtered = [(x[i], y[i]) for i in range(len(x)) if y[i] is not None]
        if not filtered:
            return {'error': '没有有效的数据点'}
            
        x = [item[0] for item in filtered]
        y = [item[1] for item in filtered]
        
        # 根据图表类型处理数据
        if chart_type == 'scatter':
            points = []
            for i in range(len(x)):
                try:
                    px = float(x[i])
                    py = float(y[i])
                    points.append({"x": px, "y": py})
                except (ValueError, TypeError):
                    continue
            if not points:
                return {'error': '无法将数据转换为散点图格式'}
            return {
                'type': 'scatter',
                'labels': x,
                'dataset_label': f'{x_field} vs {y_field}',
                'data': points
            }
            
        elif chart_type == 'histogram':
            try:
                y_numeric = [float(val) for val in y if val is not None]
                if not y_numeric:
                    return {'error': '没有有效的数值数据用于直方图'}
                counts, bin_edges = np.histogram(y_numeric, bins='auto')
                labels = [f"{round(bin_edges[i],2)}~{round(bin_edges[i+1],2)}" for i in range(len(bin_edges)-1)]
                return {
                    'type': 'bar',
                    'labels': labels,
                    'dataset_label': f'{y_field} 直方图',
                    'data': counts.tolist()
                }
            except Exception as e:
                return {'error': f'生成直方图失败: {str(e)}'}
                
        elif chart_type == 'box':
            try:
                groups = {}
                for xi, yi in zip(x, y):
                    try:
                        yi = float(yi)
                        groups.setdefault(xi, []).append(yi)
                    except (ValueError, TypeError):
                        continue
                if not groups:
                    return {'error': '没有有效的数值数据用于箱型图'}
                    
                labels = list(groups.keys())
                box_data = []
                for label in labels:
                    arr = np.array(groups[label])
                    if len(arr) == 0:
                        box_data.append([0,0,0,0,0])
                    else:
                        q1 = np.percentile(arr, 25)
                        median = np.percentile(arr, 50)
                        q3 = np.percentile(arr, 75)
                        minv = np.min(arr)
                        maxv = np.max(arr)
                        box_data.append([minv, q1, median, q3, maxv])
                return {
                    'type': 'boxplot',
                    'labels': labels,
                    'dataset_label': f'{y_field} 箱型图',
                    'data': box_data
                }
            except Exception as e:
                return {'error': f'生成箱型图失败: {str(e)}'}
                
        else:  # 默认柱状图、折线图、饼图等
            return {
                'type': chart_type,
                'labels': x,
                'dataset_label': f'{y_field}',
                'data': y
            }
            
    except Exception as e:
        return {'error': f'处理图表数据时出错: {str(e)}'} 