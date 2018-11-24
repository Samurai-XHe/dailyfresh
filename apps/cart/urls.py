from django.urls import path
from .views import CartAddView, CartInfoView


app_name = 'cart'
urlpatterns = [
    path('add/', CartAddView.as_view(), name='add'),  # 添加购物车记录
    path('', CartInfoView.as_view(), name='show'),  # 购物车页面显示
]
