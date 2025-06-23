from django.db import models
from django.contrib.auth import get_user_model

from datetime import timedelta

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
    )
    short_link = models.URLField(
        'Короткая ссылка на рецепт',
        blank=True,
        null=True,
        help_text='Короткая ссылка на рецепт')

    REQUIRED_FIELDS = ['cooking_time']

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        default_related_name = 'recipes'


class Tag(models.Model):
    """Модель для тегов"""

    name = models.CharField('Название',
                            max_length=128, 
                            help_text='Название тэга')
    slug = models.SlugField('Тэг', help_text='Слаг тэга')

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'
        default_related_name = 'tags'


class Ingredient(models.Model):
    """Модель для ингредиентов."""

    class UnitOfMeasurement(models.TextChoices):
        """Задаёт константы с единицами измерения."""

        GRAM = 'g', 'Грамм'
        KILOGRAM = 'kg', 'Килограмм'
        LITER = 'l', 'Литр'
        MILLILITER = 'ml', 'Миллилитр'
        PIECE = 'pcs', 'Штука'

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

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        default_related_name = 'ingredients'


class RecipeIngredient(models.Model):
    """Промежуточная модель для связи моделя Рецепт и Ингредиент."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    amount = models.PositiveIntegerField()

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

    