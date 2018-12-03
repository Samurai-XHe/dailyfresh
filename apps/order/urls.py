from django.urls import path
from .views import OrderPlaceView, OrderCommitView, OrderPayView, CheckPayView, CommentView


app_name = 'order'
urlpatterns = [
    path('place/', OrderPlaceView.as_view(), name='place'),  # 提交订单页面显示
    path('commit/', OrderCommitView.as_view(), name='commit'),  # 订单创建
    path('pay/', OrderPayView.as_view(), name='pay'),  # 订单支付
    path('check/', CheckPayView.as_view(), name='check'),  # 查询支付结果
    path('comment/<int:order_id>/', CommentView.as_view(), name='comment'),  # 订单评论
]
