from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.core.cache import cache
from django.core.paginator import Paginator
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from order.models import OrderGoods
from django_redis import get_redis_connection


class IndexView(View):
    """
    /index
    首页
    """
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
                'promotion_banners': promotion_banners
            }
            cache.set('index_page_data', context, 3600)  # 设置缓存数据（键，值，过期时间）

        # # 获取用户购物车中的商品的数目
        # user = request.user
        # cart_count = 0
        # if user.is_authenticated:
        #     conn = get_redis_connection('default')
        #     cart_key = 'cart_%d' % user.id
        #     cart_count = conn.hlen(cart_key)

        # context.update(cart_count=cart_count)  # 加入上下文中
        return render(request, 'index.html', context)


class DetailView(View):
    """
    /goods/商品id
    商品详情页
    """
    def get(self, request, goods_id):
        try:
            sku = GoodsSKU.objects.get(pk=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))
        # 获取全部分类
        # types = GoodsType.objects.all()
        # 获取商品的评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        # 获取同一个spu的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(pk=goods_id)
        # # 获取用户购物车中的商品数目
        user = request.user
        # cart_count = 0
        if user.is_authenticated:
            conn = get_redis_connection('default')
            # cart_key = 'cart_%d' % user.id
            # cart_count = conn.hlen(cart_key)

            # 添加用户的浏览记录
            # conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            conn.lrem(history_key, 0, goods_id)  # 移除旧纪录
            conn.lpush(history_key, goods_id)  # 从列表左侧插入新纪录
            conn.ltrim(history_key, 0, 4)
        # 组织上下文
        context = {'sku': sku,
                    'sku_orders': sku_orders,
                    'new_skus': new_skus,
                    'same_spu_skus': same_spu_skus,
        }
        return render(request, 'detail.html', context)


class ListView(View):
    """
    /list/种类id/页码?sort=排序方式
    商品详情页
    """
    def get(self, request, type_id, page):
        try:
            type = GoodsType.objects.get(pk=type_id)
        except GoodsType.DoesNotExist:
            return redirect(reverse('goods:index'))
        # types = GoodsType.objects.all()
        sort = request.GET.get('sort', '')
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对数据进行分页
        paginator = Paginator(skus, 2)
        try:
            page = int(page)
        except Exception:
            page = 1
        if page > paginator.num_pages:
            page = 1
        skus_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
        # 1.总页数小于5页，页面上显示所有页码
        # 2.如果当前页是前3页，显示1-5页
        # 3.如果当前页是后3页，显示后5页
        # 4.其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        # user = request.user
        # cart_count = 0
        # if user.is_authenticated:
        #     conn = get_redis_connection('default')
        #     cart_key = 'cart_%d' % user.id
        #     cart_count = conn.hlen(cart_key)

        context = {'type': type,
                   'skus_page': skus_page,
                   'new_skus': new_skus,
                   'pages': pages,
                   'sort': sort
        }
        return render(request, 'list.html', context)
