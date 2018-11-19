import os
from django.core.mail import send_mail
from django.conf import settings
from django.template import loader
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from celery import Celery


# 在任务处理者一端加这几句
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()

app = Celery('celery_tasks.tasks', broker='redis://192.168.204.129:6379/8')


@app.task
def send_register_active_email(to_email, username, token):
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_HOST_USER
    receiver = [to_email]
    html_message = "<h1>%s,欢迎您请点击以下链接完成注册</h1><a href='%s'>%s</a>" % (username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)


@app.task
def generate_static_index_html():
    # 产生首页静态页面
    types = GoodsType.objects.all()  # 获取商品的种类信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')  # 获取首页轮播商品信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')  # 获取首页促销活动信息

    # 获取首页分类商品展示信息
    for type in types:
        image_banners = IndexTypeGoodsBanner.objects.filter(
            type=type, display_type=1).order_by('index')
        title_banners = IndexTypeGoodsBanner.objects.filter(
            type=type, display_type=0).order_by('index')
        type.image_banners = image_banners
        type.title_banners = title_banners

    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_banners': promotion_banners}

    # 使用模板
    # 1.加载模板文件，返回模板对象
    temp = loader.get_template('static_index.html')
    # 2.渲染模板
    static_index_html = temp.render(context)

    # 生成首页对应静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/static_index.html')
    with open(save_path, 'w') as f:
        f.write(static_index_html)

