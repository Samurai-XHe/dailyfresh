import re
from django.shortcuts import render, redirect, reverse
from django.views.generic import View
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from .models import User
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
        user = User.objects.create_user(username=username, email= email, password=password)
        user.is_active = 0
        user.save()
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()
        url = 'http://localhost:8000/user/active/%s' % token

        # 发送验证邮件
        subject = '注册激活链接'
        message = ''
        from_email = '847834358@qq.com'
        to_email = [email]
        html_message = "<h1>请点击以下链接完成注册</h1><a href='%s'>%s</a>" %(url, url)
        send_mail(subject, message, from_email, to_email, html_message=html_message)
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


class LoginView(View):
    def get(self, request):
        return render(request, 'login.html', {})
