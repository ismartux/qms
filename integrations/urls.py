from django.urls import path
from . import views
from integrations.bitable.snapshot_receiver import receive_bitable_snapshot

app_name = "bitable"

urlpatterns = [
    
    path("send-lark-broadcast/", views.bitable_send_lark_broadcast, name="bitable_send_lark_broadcast"),
    path(
        "internal/bitable/snapshot/",
        receive_bitable_snapshot,
        name="receive_bitable_snapshot",
    ),

]