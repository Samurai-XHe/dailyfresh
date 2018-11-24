from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin


class CartAddView(View):
    """
    /cart/add
    添加购物车记录
    """
    def post(self, request):
        user = request.user

        # 判断用户是否登录(因为是ajax请求所以不能用继承LoginRequiredMixin的方式)
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '请先登录'})

        # 接收数据
        sku_id = request.POST.get('sku_id', '')
        count = request.POST.get('count', '')

        # 数据效验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})

        # 效验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})

        # 效验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理:添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 尝试获取sku_id的值，不存在则添加，存在则累加
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 存在则累加
            count += int(cart_count)

        # 效验商品库存
        if count > sku.stock:
            return JsonResponse({'res':4, 'errmsg': '商品库存不足'})

        # 设置hash中sku_id对应的值
        # hset->如果sku_id已经存在，更新数据， 如果sku_id不存在，添加数据
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车商品条目数
        total_count = conn.hlen(cart_key)

        return JsonResponse({'res': 5, 'total_count': total_count, 'errmsg': '添加成功'})


class CartInfoView(LoginRequiredMixin, View):
    """
    /cart/
    购物车页面展示
    """
    def get(self, request):
        user = request.user
        conn = get_redis_connection('default')

        # 获取用户购物车中商品的信息
        cart_key = 'cart_%d' % user.id
        cart_dict = conn.hgetall(cart_key)

        # 保存用户购物车中商品的总数目和总价格
        skus = []
        total_count = 0
        total_price = 0
        # 遍历获取商品的信息
        for sku_id, count in cart_dict.items():
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(pk=sku_id)
            # 计算商品的小计
            amount = int(count) * sku.price
            # 动态给sku对象添加一个小计属性
            sku.amount = amount
            # 动态给sku对象添加一个count属性
            sku.count = count.decode()
            skus.append(sku)

            # 累计计算商品的总价和总数
            total_count += int(count)
            total_price += amount

        context = {
            'total_count': total_count,
            'total_price': total_price,
            'skus': skus}
        return render(request, 'cart.html', context)


