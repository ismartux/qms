from django.urls import path
from . import views

app_name = "ehs"

urlpatterns = [
    path("home/", views.ehs_home, name="ehs_home"),
    path("daily/", views.ehs_daily_template_list, name="ehs_daily_template_list"),
    path("special/", views.ehs_special_template_list, name="ehs_special_template_list"),
    path("start/<int:template_id>/", views.ehs_start_submission, name="start_submission"),
    path("fill/<uuid:pk>/", views.ehs_fill_submission, name="fill_submission"),
    path("submit/<uuid:pk>/", views.ehs_submit_submission, name="submit_submission"),
    
    path("scan/", views.ehs_qr_scanner, name="ehs_qr_scanner"),
    
    path("submissions/", views.ehs_submission_list, name="ehs_submission_list"),
    path("submission/<uuid:pk>/popup/", views.ehs_submission_popup, name="ehs_submission_popup"),
    path("notifications/", views.ehs_notification_list, name="ehs_notification_list"),
    path("notifications/read/<int:pk>/", views.ehs_mark_notification_read, name="ehs_mark_notification_read"),
    
    path("admin/submissions/", views.ehs_admin_submission_list, name="ehs_admin_submission_list"),
]