import re

from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.core.paginator import Paginator

from .models import User, Address
from order.models import OrderInfo, OrderGoods
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from celery_tasks.tasks import send_register_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired


class RegisterView(View):
    """
    /user/register
    注册页面
    """
    def get(self, request):
        return render(request, 'register.html', {})

    def post(self, request):
        username = request.POST.get('user_name', '')
        password = request.POST.get('pwd', '')
        c_password = request.POST.get('cpwd', '')
        email = request.POST.get('email', '')
        allow = request.POST.get('allow', '')
        # 进行数据效验
        if not all([username, password, c_password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        # 效验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})
        # 效验用户是否已存在
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = None
        if user:
            return render(request, 'register.html', {'errmsg': '邮箱已存在'})

        # 进行业务处理
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = 0
        user.save()
        # 生成加密对象，第一个参数是加密类型，可以使用settings中的SECRET_KEY，第二个参数为过期时间，单位s
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}  # 加密的内容为用户id的字典
        token = serializer.dumps(info)  # 加密
        token = token.decode()  # 加密后的信息是二进制，所以要解码
        token = 'http://localhost:8000/user/active/%s' % token  # 拼接成完整的验证链接

        # 发送验证邮件
        send_register_active_email.delay(email, username, token)
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """
    /user/active
    激活用户
    """
    def get(self, request, token):
        # 解析加密信息前也要实例化一个对象，参数要与之前一致
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)  # 解密
            user_id = info['confirm']  # 获取用户id
            user = User.objects.get(pk=user_id)
            user.is_active = 1  # 激活用户
            user.save()
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活链接已过期')


class LoginView(View):
    """
    /user/login
    登录页面
    """
    def get(self, request):
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username', '')  # 取出用户名
            checked = 'checked'  # 在前端显示checked选中状态。
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {
            'username': username,
            'checked': checked
        })

    def post(self, request):
        username = request.POST.get('username', '')
        password = request.POST.get('pwd', '')
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})
        user = authenticate(username=username, password=password)
        if user:
            if user.is_active:
                login(request, user)
                next_url = request.GET.get('next', reverse('goods:index'))
                response = redirect(next_url)
                remember = request.POST.get('remember', '')
                if remember == 'on':  # 判断是否记住用户名，如果是，在cookie中加入用户名信息
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')  # 如过否，删除cookie中的用户名信息
                return response
            else:
                return render(request, 'login.html', {'errmsg': '用户未激活'})
        else:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})


class LogoutView(View):
    """
    /user/logout
    注销登陆页面
    """
    def get(self, request):
        logout(request)
        return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiredMixin, View):
    """
    /user/user
    用户中心-信息页
    """
    def get(self, request):
        user = request.user
        address = Address.objects.get_default_address(user=user)
        # 从redis获取最近5条浏览记录
        con = get_redis_connection('default')
        history_key = 'history_%d' % user.id  # 利用用户id获取key值
        sku_ids = con.lrange(history_key, 0, 4)  # 获取对应的5个商品id
        goods_li = []
        # 按顺序获取五条商品记录
        for sku_id in sku_ids:
            goods = GoodsSKU.objects.get(pk=sku_id)
            goods_li.append(goods)
        return render(request, 'user_center_info.html', {
            'page': 'user',
            'address': address,
            'goods_li': goods_li
        })


class OrderView(LoginRequiredMixin, View):
    """
    /user/order
    用户中心-订单页
    """
    def get(self, request, page):
        '''显示'''
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count * order_sku.price
                # 动态给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount = amount

            # 动态给order增加属性，保存订单状态标题
            # order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 3)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

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

        # 组织上下文
        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'}

        # 使用模板
        return render(request, 'user_center_order.html', context)


class AddressView(LoginRequiredMixin, View):
    """
    /user/address
    用户中心-地址页
    """
    def get(self, request):
        user = request.user
        address = Address.objects.get_default_address(user=user)  # 获取默认地址信息
        return render(request, 'user_center_site.html', {
            'page': 'address',
            'address': address
        })

    def post(self, request):
        receiver = request.POST.get('receiver', '')
        addr = request.POST.get('addr', '')
        zip_code = request.POST.get('zip_code', '')
        phone = request.POST.get('phone', '')
        user = request.user
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})
        if not re.match(r"^1[34578][0-9]{9}$", phone):
            return render(request, 'user_center_site.html', {
                'errmsg': '手机格式不正确',
                'receiver': receiver,
                'addr': addr,
                'zip_code': zip_code,
            })
        address = Address.objects.get_default_address(user=user)
        if address:
            is_default = False
        else:
            is_default = True
        Address.objects.create(
            user = request.user,
            receiver=receiver,
            addr=addr,
            zip_code=zip_code,
            phone=phone,
            is_default=is_default
        )
        return redirect(reverse('user:address'))
