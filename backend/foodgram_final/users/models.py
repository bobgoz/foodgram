from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Дополняет основную модель пользователя
    полями avatar и is_subscribed."""

    email = models.EmailField(unique=True)
    avatar = models.BinaryField('Картинка, закодированная в Base64')
    is_subscribed = models.BooleanField('Подписка', default=False)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        default_related_name = 'users'
