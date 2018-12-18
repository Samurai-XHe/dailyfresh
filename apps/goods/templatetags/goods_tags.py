from django import template
from django_redis import get_redis_connection
from goods.models import GoodsType

register = template.Library()

@register.simple_tag()
def get_goods_number(user):
	# 获取用户购物车中的商品的数目
    cart_count = 0
    if user.is_authenticated:
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        cart_count = conn.hlen(cart_key)
        return cart_count
    else:
    	return cart_count


@register.simple_tag()
def get_goods_type():
	types = GoodsType.objects.all()
	return types