from django.urls import path
from . import views

app_name = "bitable"

urlpatterns = [
    
    path("send-lark-broadcast/", views.bitable_send_lark_broadcast, name="bitable_send_lark_broadcast"),

]