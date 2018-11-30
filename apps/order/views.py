from datetime import datetime
import os

from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.http import JsonResponse
from django.db import transaction
from django.conf import settings

from goods.models import GoodsSKU
from user.models import Address
from .models import OrderInfo, OrderGoods

from django_redis import get_redis_connection
from alipay import AliPay

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
    @transaction.atomic  # django事务
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

        # 设置事务保存点
        save_id = transaction.savepoint()

        try:
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
                # 乐观锁，尝试三次
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(pk=sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
                    # 从redis中获取用户所要购买的商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # 判断商品的库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res': 6, 'errmsg': '商品库存不足'})

                    # todo: 更新商品的库存和销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - int(count)
                    new_sales = sku.sales + int(count)
                    sku.save()

                    # 返回受影响的行数，能查到说明库存没变，可以更新，查不到说明原库存已经变化，不能直接更新，要重新循环一次
                    res = GoodsSKU.objects.filter(id=sku.id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 尝试的第三次
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res': 7, 'errmsg': '下单失败2'})
                        continue

                    # todo: 向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=count,
                        price=sku.price
                    )

                    # todo: 累加计算商品的总数量和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount
                    break

            # todo: 更新订单信息表中的商品的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res': 7, 'errmsg': '下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)

        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        return JsonResponse({'res': 5, 'message': '创建成功'})


class OrderPayView(View):
    """
    /order/pay
    ajax post
    前端传递的参数:订单id(order_id)
    """
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(
                order_id = order_id,
                user = user,
                pay_method = 3,
                order_status = 1
            )
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'订单错误'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid = "2016092300580591",
            app_notify_url = None,  # 默认回调url
            app_private_key_string = settings.APP_PRIVATE_KEY_STRING,  # 应用的私匙
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string = settings.ALIPAY_PUBLIC_KEY_STRING,
            sign_type = "RSA2",  # RSA 或者 RSA2
            debug = True,  # 默认False
        )

        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price  # Decimal
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no = order_id,  # 订单id
            total_amount = str(total_pay),  # 支付总金额
            subject = '天天生鲜%s' % order_id,
            return_url = None,
            notify_url = None # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res': 3, 'pay_url': pay_url})
