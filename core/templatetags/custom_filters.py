from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    从字典中获取指定键的值
    用法: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return ''
    return dictionary.get(key, '') 