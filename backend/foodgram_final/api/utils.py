from django.conf import settings
from django.core.mail import send_mail


def send_confirm_mail(user, confirmation_code):
    """
    Отправка кода подтверждения на email пользователя.
    """

    subject = 'Foodgram registration'
    message = (f'Здравствуйте, {user.username}! '
               f'Ваш код подтверждения:\n{confirmation_code}')
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    return send_mail(
        subject,
        message,
        from_email,
        recipient_list,
        fail_silently=False
    )
