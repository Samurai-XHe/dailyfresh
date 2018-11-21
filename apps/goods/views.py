from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.core.cache import cache
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from order.models import OrderGoods
from django_redis import get_redis_connection


# 首页 /index
class IndexView(View):
    def get(self, request):
        context = cache.get('index_page_data')  # 获取缓存数据
        if context is None:  # 没有的话就获取数据
            types = GoodsType.objects.all()  # 获取商品的种类信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index')  # 获取首页轮播商品信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')  # 获取首页促销活动信息

            # 获取首页分类商品展示信息
            for tp in types:
                image_banners = IndexTypeGoodsBanner.objects.filter(
                    type=tp, display_type=1).order_by('index')
                title_banners = IndexTypeGoodsBanner.objects.filter(
                    type=tp, display_type=0).order_by('index')
                tp.image_banners = image_banners
                tp.title_banners = title_banners

            context = {
                'types': types,
                'goods_banners': goods_banners,
                'promotion_banners': promotion_banners}
            cache.set('index_page_data', context, 3600)  # 设置缓存数据（键，值，过期时间）

        # 获取用户购物车中的商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        context.update(cart_count=cart_count)  # 加入上下文中
        return render(request, 'index.html', context)


# 商品详情页 /goods/商品id
class DetailView(View):
    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(pk=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))
        # 获取全部分类
        types = GoodsType.objects.all()
        # 获取商品的评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        # 获取同一个spu的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(pk=goods_id)
        # 获取用户购物车中的商品数目
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

            # 添加用户的浏览记录
            # conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            conn.lrem(history_key, 0, goods_id)  # 移除旧纪录
            conn.lpush(history_key, goods_id)  # 从列表左侧插入新纪录
            conn.ltrim(history_key, 0, 4)
        # 组织上下文
        context = {'sku': sku,
                   'types': types,
                    'sku_orders': sku_orders,
                    'new_skus': new_skus,
                    'same_spu_skus': same_spu_skus,
                    'cart_count': cart_count}
        return render(request, 'detail.html', context)

