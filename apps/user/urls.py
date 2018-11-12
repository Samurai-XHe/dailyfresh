from django.urls import path, re_path
from .views import RegisterView, ActiveView, LoginView


app_name = 'user'
urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    re_path(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    path('login/', LoginView.as_view(), name='login')
]
