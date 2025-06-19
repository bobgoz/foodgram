from django.conf import settings
from django.core.mail import send_mail
from drf_base64.fields import Base64ImageField
import base64


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


class Base64BinaryField(Base64ImageField):
    def to_internal_value(self, data):
        # Получаем бинарные данные из родительского класса
        file_object = super().to_internal_value(data)
        
        # Преобразуем ContentFile в bytes
        if hasattr(file_object, 'read'):
            return file_object.read()
        return file_object

    def to_representation(self, value):
        if not value:
            return None
        
        # Если значение уже в bytes - кодируем в base64
        if isinstance(value, bytes):
            return f"data:image/jpeg;base64,{base64.b64encode(value).decode()}"
        
        return super().to_representation(value)