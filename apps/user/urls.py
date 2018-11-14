from django.urls import path, re_path
from .views import RegisterView, ActiveView, LoginView, LogoutView, UserInfoView, OrderView, AddressView


app_name = 'user'
urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),  # 注册
    re_path(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),  # 注册激活
    path('login/', LoginView.as_view(), name='login'),  # 登录
    path('logout/', LogoutView.as_view(), name='logout'),  # 注销登录
    path('user/', UserInfoView.as_view(), name='user'),  # 用户中心-信息页
    path('order/', OrderView.as_view(), name='order'),  # 用户中心-订单也
    path('address/', AddressView.as_view(), name='address'),  # 用户中心-地址页
]
