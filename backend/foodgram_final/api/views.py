import base64
import filetype
from io import BytesIO

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum
from django.views import View

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework import status
from rest_framework.mixins import (ListModelMixin,
                                   RetrieveModelMixin,
                                   )
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from djoser.views import UserViewSet

from foodgram.models import (
    Recipe,
    Tag,
    Ingredient,
    ShoppingCart,
    Subscription,
    RecipeIngredient,
    Favorite,
    Token,
)

from .serializers import (
    RecipeSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    UserSerializer,
    SubscriptionSerializer,
    FavoriteSerializer,
)
from .permissions import IsRecipeOwnerPermission
from .filters import RecipeFilter

from .paginations import (
    RecipeCustomPagination,
    LimitPageNumberPagination,
)

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    """Кастомный ViewSet на основе Djoser UserViewSet."""

    pagination_class = LimitPageNumberPagination
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend,)

    def get_permissions(self):
        """Задает пермишены для определенных действий."""
        if self.action == 'me':
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    def get_queryset(self):
        """Использует prefetch_related для оптимизации запросов."""
        return User.objects.prefetch_related('following').all()

    @action(detail=True, methods=['POST', 'DELETE'])
    def subscribe(self, request, id=None):
        """Создаёт эндпоинт для подписки на пользователей и отписки."""

        author = get_object_or_404(User, pk=id)
        user = request.user

        if request.method == 'POST' and user == author:
            return Response(
                {'error': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.method == 'POST':
            if Subscription.objects.filter(user=user, author=author).exists():
                return Response(
                    {'error': 'Вы уже подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = SubscriptionSerializer(author,
                                                data={},
                                                context={'request': request,
                                                         'author': author,
                                                         })
            serializer.is_valid(raise_exception=True)

            Subscription.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            subscription = Subscription.objects.filter(
                user=user, author=author)
            if not subscription.first():
                return Response(
                    {'error': 'Такой подписки не существует.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['PUT', 'DELETE'], url_path='me/avatar')
    def load_and_delete_avatar(self, request, pk=None):
        """Создаёт эндпоинт для добавления/удаления аватара"""

        user = request.user

        if request.method == 'PUT':
            avatar_data = request.data.get('avatar')

            if not avatar_data:
                return Response(
                    {'avatar': 'Обязательное поле'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                format, imgstr = avatar_data.split(';base64,')
                img_bytes = base64.b64decode(imgstr)

                # Проверяем тип изображения через filetype
                kind = filetype.guess(img_bytes)
                if kind is None or kind.mime not in ['image/jpeg',
                                                     'image/png', 'image/gif']:
                    return Response(
                        {"error": "Invalid image format. Only JPEG,"
                         "PNG, and GIF are allowed."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                ext = kind.extension
                data = ContentFile(img_bytes, name=f'avatar_{user.id}.{ext}')
                user.avatar.save(f'avatar_{user.id}.{ext}', data, save=True)

                return Response(
                    {"avatar": request.build_absolute_uri(user.avatar.url)},
                    status=status.HTTP_200_OK
                )

            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

        elif request.method == 'DELETE':
            if not user.avatar:
                return Response(
                    {"error": "No avatar to delete"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.avatar.delete(save=True)
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['GET'],
        permission_classes=[IsAuthenticated],
    )
    def subscriptions(self, request, pk=None):
        """Создаёт эндпоинт, который возвращает
        список пользователей на которых подписан
        текущий пользователь.
        """

        subscribed_users = User.objects.filter(following__user=request.user)
        return self.get_paginated_response(
            SubscriptionSerializer(
                self.paginate_queryset(subscribed_users),
                many=True,
                context={'request': request},
            ).data
        )


class RecipeViewSet(ModelViewSet):
    """ViewSet для модели Рецепт"""

    queryset = Recipe.objects.all()
    permission_classes = [IsRecipeOwnerPermission]
    pagination_class = RecipeCustomPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    # def create(self, request, *args, **kwargs):
    #     try:
    #         return super().create(request, *args, **kwargs)
    #     except IntegrityError as e:
    #         return Response(
    #             {
    #                 'error': 'Ошибка целостности данных',
    #                 'detail': str(e)
    #             },
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    def get_serializer_class(self):
        if self.action in SAFE_METHODS:
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

    def create(self, request, *args, **kwargs):
        """Проверка наличия ингредиентов перед созданием."""

        if 'ingredients' in request.data:
            for ingredient in request.data['ingredients']:
                ingr_id = ingredient['id']
                if not Ingredient.objects.filter(id=ingr_id).exists():
                    return Response(
                        {'error': f'Ингредиент с id={ingr_id} не найден.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Проверка наличия ингредиентов перед обновлением."""

        if 'ingredients' in request.data:
            for ingredient in request.data['ingredients']:
                ingr_id = ingredient['id']
                if not Ingredient.objects.filter(id=ingr_id).exists():
                    return Response(
                        {'error': f'Ингредиент с id={ingr_id} не найден.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=['POST', 'DELETE'],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        """Эндпоинт для добавления в избранные рецепты."""

        recipe = self.get_object()
        user = request.user

        if request.method == 'POST':
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {"error": "Рецепт уже в избранном."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            Favorite.objects.create(user=user, recipe=recipe)
            serializer = FavoriteSerializer(
                recipe,
                context={"request": request},
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == "DELETE":
            # Проверяем, есть ли рецепт в избранном
            favorite = Favorite.objects.filter(
                user=user, recipe=recipe).first()
            if not favorite:
                return Response(
                    {"error": "Рецепта нет в избранном."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            favorite.delete()
            serializer = FavoriteSerializer(
                recipe,
                context={"request": request},
            )
            return Response(serializer.data, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['GET'], url_path='get-link')
    def get_link(self, request, pk=None):
        """
        Эндпоинт для генерации или возврата короткой ссылки на рецепт.
        """

        recipe = self.get_object()

        full_url = request.build_absolute_uri(recipe.get_absolute_url())

        # Проверяем существование токена или генерируем новый.
        token, created = Token.objects.get_or_create(
            full_url=full_url,
            defaults={
                'is_active': True,
            }
        )

        # Обновляем счетчик, если ссылка существует.
        if not created:
            token.requests_count += 1
            token.save()

        # Возвращаем короткую ссылку.
        short_link = f'{settings.BASE_SHORT_URL}/{token.short_url}'
        return Response(
            {'short-link': short_link},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['GET'])
    def download_shopping_cart(self, request, pk=None):
        """Генерирует PDF списком покупок."""

        # данные для PDF
        shopping_list = self._generate_shopping_list(request.user)

        # Регистрация шрифта
        pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))

        # Создание PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)

        # Настройки документа
        p.setFont('DejaVu', 12)
        y_position = 750

        # Заголовок
        p.drawString(100, y_position, 'Список покупок')
        y_position -= 30

        # Содержимое
        for item in shopping_list:
            amount = item.get('total', 0)
            text = f"""- {item['ingredient__name']}
            ({amount} {item['ingredient__measurement_unit']})"""
            p.drawString(100, y_position, text)
            y_position -= 20

            if y_position < 50:  # Если конец страницы
                p.showPage()
                y_position = 750
                p.setFont("Helvetica", 12)

        p.save()

        # Возвращение PDF как ответ
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = ('attachment; filename='
                                           '"shopping_list.pdf"')
        return response

    def _generate_shopping_list(self, user):
        """Генерирует список ингредиентов."""

        return (
            RecipeIngredient.objects
            .filter(recipe__in_shopping_carts__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total=Sum('amount'))
            .order_by('ingredient__name')
        )

    @action(detail=True, methods=['POST', 'DELETE'])
    def shopping_cart(self, request, pk=None):
        """Создаёт эндпоинт для добавления рецепта
        в список покупок и его удаления.
        """

        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == 'POST':
            shopping_cart = ShoppingCart.objects.filter(
                user=request.user, recipe=recipe)
            if shopping_cart.exists():
                return Response(
                    {'error': 'Рецепт уже есть в корзине покупок.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ShoppingCart.objects.create(user=request.user, recipe=recipe)
            response_data = {
                'id': recipe.id,
                'name': recipe.name,
                'image': request.build_absolute_uri(
                    recipe.image.url) if recipe.image else None,
                'cooking_time': recipe.cooking_time
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            try:
                cart_item = ShoppingCart.objects.get(
                    recipe=recipe,
                    user=request.user)
                cart_item.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except ShoppingCart.DoesNotExist:
                return Response(
                    {'error': 'Данного рецепта нет в корзине покупок!'},
                    status=status.HTTP_400_BAD_REQUEST)


class TagViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    """ViewSet для модели Тэг"""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    """ViewSet для модели Ингредиент"""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (SearchFilter,)
    search_fields = ('^name',)


class SubscriptionViewSet(ModelViewSet):
    """ViewSet для модели Подписки."""

    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = pagination.LimitOffsetPagination

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class ShortLinkRedirectView(View):
    """Обрабатывает переход по короткой ссылке."""

    def get(self, request, short_url):

        token = get_object_or_404(Token, short_url=short_url, is_active=True)

        token.requests_count += 1
        token.save()

        return redirect(token.full_url)
