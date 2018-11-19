from django.shortcuts import render
from django.views.generic import View
from django.core.cache import cache
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
# from django_redis import get_redis_connection


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
        # user = request.user
        # cart_count = 0
        # if user.is_authenticated():
        #     conn = get_redis_connection('default')
        #     cart_key = 'cart_%d' % user.id
        #     cart_count = conn.hlen(cart_key)
        #
        # context.update(cart_count=cart_count)  # 加入上下文中
        return render(request, 'index.html', context)
