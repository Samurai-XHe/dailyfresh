import re
from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from .models import User
from celery_tasks.tasks import send_register_active_email
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired


# /user/register  注册页面
class RegisterView(View):
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
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()
        token = 'http://localhost:8000/user/active/%s' % token

        # 发送验证邮件
        send_register_active_email.delay(email, username, token)
        return redirect(reverse('goods:index'))


# 激活用户
class ActiveView(View):
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            user = User.objects.get(pk=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活链接已过期')


# /user/login
class LoginView(View):
    def get(self, request):
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username', '')
            checked = 'checked'
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
                response = redirect(reverse('goods:index'))
                remember = request.POST.get('remember', '')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                return render(request, 'login.html', {'errmsg': '用户未激活'})
        else:
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})

