from datetime import datetime

from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.http import JsonResponse

from goods.models import GoodsSKU
from user.models import Address
from .models import OrderInfo, OrderGoods

from django_redis import get_redis_connection

class OrderPlaceView(View):
    """
    /order/place
    提交订单页面显示
    """
    def post(self, request):
        user = request.user
        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids', '')
        if not sku_ids:
            return redirect(reverse('cart:show'))
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        skus = []
        # 保存商品的总件数和总价格
        total_price = 0
        total_count = 0
        # 遍历skus获取用户要购买的商品信息
        for id in sku_ids:
            try:
                sku = GoodsSKU.objects.get(pk=id)
            except GoodsSKU.DoesNotExist as e:
                return redirect(reverse('cart:show'))
            count = conn.hget(cart_key, id)
            amount = sku.price * int(count)
            sku.count = count.decode()
            sku.amount = amount
            skus.append(sku)
            total_price += int(amount)
            total_count += int(count)

        # 运费
        transit_price = 10

        # 实付款
        total_pay = total_price + transit_price

        # 获取用户的收件地址
        address = Address.objects.filter(user=user)

        # 组织上下文
        sku_ids = ','.join(sku_ids)
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transit_price': transit_price,
            'total_pay': total_pay,
            'address': address,
            'sku_ids': sku_ids,
        }
        return render(request, 'place_order.html', context)


class OrderCommitView(View):
    """
    todo: 订单创建
    前端传递的参数:地址id(addr_id) 支付方式(pay_method) 用户要购买的商品id字符串(sku_ids)
    mysql事务: 一组sql操作，要么都成功，要么都失败
    高并发:秒杀
    支付宝支付
    """
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        addr_id = request.POST.get('addr_id', '')
        pay_method = request.POST.get('pay_method', '')
        sku_ids = request.POST.get('sku_ids', '')

        # 参数效验
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})

        # 效验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的支付方式'})

        # 效验地址
        try:
            addr = Address.objects.get(pk=addr_id)
        except Address.DoesNotExist as e:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})

        # todo: 创建订单核心业务
        # 组织参数
        # 订单ID：20180606181630+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)

        # 运费
        transit_price = 10

        # 总数目和总金额
        total_count = 0
        total_price = 0

        # todo: 向df_order_info表中添加一条记录
        order = OrderInfo.objects.create(
            order_id=order_id,
            user = user,
            addr = addr,
            pay_method=pay_method,
            total_count=total_count,
            total_price=total_price,
            transit_price=transit_price,
        )

        # todo: 用户的订单中有几个商品，需要向df_order_goods表中加入几条记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id

        sku_ids = sku_ids.split(',')
        for sku_id in sku_ids:
            try:
                sku = GoodsSKU.objects.get(pk=sku_id)
            except GoodsSKU.DoesNotExist:
                return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
            count = conn.hget(cart_key, sku_id)
            # todo: 向df_order_goods表中添加一条记录
            OrderGoods.objects.create(
                order = order,
                sku=sku,
                count = count,
                price = sku.price
            )
            # todo: 更新商品的库存和销量
            sku.stock -= int(count)
            sku.sales += int(count)
            sku.save()

            # todo: 累加计算商品的总数量和总价格
            amount = sku.price * int(count)
            total_count += int(count)
            total_price += amount

        # todo: 更新订单信息表中的商品的总数量和总价格
        order.total_count = total_count
        order.total_price = total_price
        order.save()

        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res': 5, 'message': '创建成功'})
