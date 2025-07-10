from django.db import models
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import validators

from random import choices

User = get_user_model()


class Recipe(models.Model):
    """Модель для рецептов."""

    author = models.ForeignKey(User,
                               verbose_name='Автор',
                               on_delete=models.CASCADE)
    name = models.CharField('Название', max_length=256)
    text = models.TextField('Описание')
    ingredients = models.ManyToManyField(
        'Ingredient',
        through='RecipeIngredient',
        through_fields=('recipe', 'ingredient'),
        verbose_name='Список ингредиентов')
    image = models.ImageField(
        'Фотография блюда',
        upload_to='recipes/images',
        null=False,
        default=None,
    )
    tags = models.ManyToManyField(
        'Tag', verbose_name='id тегов')
    cooking_time = models.IntegerField(
        'Время приготовления',
        help_text='Длительность приготовления в минутах.',
        blank=False,
        validators=[validators.MinValueValidator(1)],
    )
    short_link = models.URLField(
        'Короткая ссылка на рецепт',
        blank=True,
        null=True,
        help_text='Короткая ссылка на рецепт')
    created_at = models.DateTimeField(
        "Дата добавления",
        auto_now_add=True,
        db_index=True,
        null=True,
        blank=True,
    )

    REQUIRED_FIELDS = ['cooking_time']

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        default_related_name = 'recipes'
        ordering = ['-created_at']

    def get_absolute_url(self):
        """
        Удаление префикса 'api/', если он есть,
        и возвращение полной ссылки.
        """
        return reverse(
            'recipe-detail', kwargs={'pk': self.pk}).replace('api/', '', 1)


class Tag(models.Model):
    """Модель для тегов"""

    name = models.CharField('Название',
                            max_length=128,
                            help_text='Название тэга')
    slug = models.SlugField(
        'Слаг',
        help_text='Слэг тэга',
        unique=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'
        default_related_name = 'tags'


class Ingredient(models.Model):
    """Модель для ингредиентов."""

    class UnitOfMeasurement(models.TextChoices):
        """Задаёт константы с единицами измерения."""

        GRAM = 'г', 'Грамм'
        KILOGRAM = 'кг', 'Килограмм'
        LITER = 'л', 'Литр'
        MILLILITER = 'мл', 'Миллилитр'
        PIECE = 'шт', 'Штука'

    name = models.CharField(
        'Название',
        max_length=256,
        help_text='Название ингредиента'
    )
    measurement_unit = models.CharField(
        'Единица измерения',
        max_length=10,
        choices=UnitOfMeasurement.choices,
        help_text='Единица измерения',
    )

    def __str__(self):
        return self.name

    @property
    def favorites_count(self):
        return self.favorites.count()

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        default_related_name = 'ingredients'


class RecipeIngredient(models.Model):
    """Промежуточная модель для связи моделя Рецепт и Ингредиент."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipe_ingredients',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
    )
    amount = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['recipe', 'ingredient'],
                name='unique_ingredient_in_recipe'
            )
        ]


class ShoppingCart(models.Model):
    """Модель для Списка Покупок."""

    recipe = models.ForeignKey(Recipe,
                               on_delete=models.CASCADE,
                               verbose_name='Рецепт',
                               related_name='in_shopping_carts',
                               )
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             verbose_name='Пользователь',
                             related_name='shopping_cart',
                             )
    added_at = models.DateTimeField('Дата и время добавления в список покупок',
                                    auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_user_recipe_in_cart',
            )
        ]
        verbose_name = 'Корзина покупок'
        verbose_name_plural = 'Корзины покупок'

    def __str__(self):
        return f'{self.user} -> {self.recipe}'


class Subscription(models.Model):
    """Модель для Подписок."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Подписчик',
        related_name='follower',
    )
    author = models.ForeignKey(
        User,
        verbose_name='Автор',
        on_delete=models.CASCADE,
        related_name='following',
    )
    created_at = models.DateTimeField(
        'Дата подписки',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            # Запрещает дублирование подписки
            models.UniqueConstraint(
                fields=['user', 'author'],
                name='unique_subscription'
            ),
            # Запрещает подписку на себя.
            models.CheckConstraint(
                check=~models.Q(user=models.F('author')),
                name='prevent_self_subscription'
            )
        ]

    def __str__(self):
        return f'{self.user} подписан на {self.author}'


class Favorite(models.Model):
    """Модель для Избранного."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )
    added_at = models.DateTimeField(
        'Дата добавления в список',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные'
        default_related_name = 'favorites'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_favorite'
            )
        ]

    def __str__(self):
        return f'{self.user} добавил {self.recipe} в избранное'


class Token(models.Model):
    """
    Модель для хранения токенов (наборов символов)
    для коротких ссылок.
    """

    full_url = models.URLField('Полная ссылка', unique=True)
    short_url = models.CharField(
        'Короткая ссылка',
        max_length=20,
        unique=True,
        db_index=True,
        blank=True,
    )
    requests_count = models.IntegerField(
        'Счётчик запросов к ссылке',
        default=0,
    )
    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True,
    )
    is_active = models.BooleanField(
        'Наличие короткой ссылки.',
        default=False,
    )

    class Meta:
        verbose_name = 'Токен'
        verbose_name_plural = 'Токены'
        ordering = ('-created_at',)

    @classmethod
    def generate_short_url(cls):
        """Генерирует уникальный короткий URL"""
        while True:
            short_url = ''.join(choices(settings.CHARACTERS,
                                        k=settings.TOKEN_LENGTH))
            if not cls.objects.filter(short_url=short_url).exists():
                return short_url

    def save(self, *args, **kwargs):
        if not self.short_url:
            self.short_url = self.generate_short_url()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.full_url} -> {self.short_url}'
