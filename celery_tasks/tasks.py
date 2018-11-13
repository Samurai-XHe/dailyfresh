from django.core.mail import send_mail
from django.conf import settings
from celery import Celery


app = Celery('celery_tasks.tasks', broker='redis://192.168.1.110:6379/8')


@app.task
def send_register_active_email(to_email, username, token):
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_HOST_USER
    receiver = [to_email]
    html_message = "<h1>%s,欢迎您请点击以下链接完成注册</h1><a href='%s'>%s</a>" % (username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)
