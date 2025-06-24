from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class User(AbstractUser):
    """Дополняет основную модель пользователя
    полями avatar и is_subscribed."""

    email = models.EmailField('Электронная почта', unique=True)
    username = models.CharField('Имя пользователя',
                                unique=True, max_length=150, blank=False)
    avatar = models.ImageField(
        'Картинка',
        upload_to='recipes/images/',
        null=True,
        default=None,
    )
    is_subscribed = models.BooleanField('Подписка', default=False)
    is_active = models.BooleanField(default=True)
    first_name = models.CharField('Имя', max_length=150, blank=False)
    last_name = models.CharField('Фамилия', max_length=150, blank=False)

    USERNAME_FIELD = 'email'  # Используем email для входа
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        default_related_name = 'users'

