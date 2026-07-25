from ehs_engine.models import EHSNotification


class NotificationService:

    @staticmethod
    def create_notification(user, title, message, submission=None):
        return EHSNotification.objects.create(
            recipient=user,
            title=title,
            message=message,
            submission=submission
        )

    @staticmethod
    def notify_users(users, title, message, submission=None):
        for user in users:
            NotificationService.create_notification(
                user=user,
                title=title,
                message=message,
                submission=submission
            )