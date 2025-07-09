import base64
import filetype
from io import BytesIO

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce
from django.views import View

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS, IsAuthenticatedOrReadOnly
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
    IngredientRecipeSerializer,
    ShoppingCartSerializer,
    SubscribeSerializer,
    RecipeShortSerializer,
    AvatarSerializer,
)
from .permissions import CustomPermission
from .filters import RecipeFilter

from .paginations import (
    RecipeCustomPagination,
    LimitPageNumberPagination,
)

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    """Кастомный ViewSet на основе Djoser UserViewSet."""

    pagination_class = LimitPageNumberPagination
    permission_classes = (CustomPermission,)
    filter_backends = (DjangoFilterBackend,)

    def get_serializer_class(self):
        """Назначение сериализаторов для методов."""
        if self.action == 'subscribe':
            return SubscriptionSerializer
        if self.action == 'load_avatar':
            return AvatarSerializer
        if self.action == 'subscriptions':
            return SubscriptionSerializer
        return UserSerializer

    @action(detail=True, methods=['POST'])
    def subscribe(self, request, id=None):
        """Создаёт эндпоинт для подписки на пользователей и отписки."""

        author = get_object_or_404(User, pk=id)
        user = request.user

        serializer = self.get_serializer(
            data={},
            context={
                'request': request,
                'user': user,
                'autho': author,
                }
            )
        serializer.is_valid(raise_exception=True)
        author_serializer = self.get_serializer(
            author,
            context={'request': request}
        )
        serializer.save(raise_exception=True)
        return Response(author_serializer.data, 
                        status=status.HTTP_201_CREATED)

    subscribe.mapping.delete
    def subscribe_delete(self, request, id=None):
        """Удаление подписки"""

        author = get_object_or_404(User, pk=id)
        Subscription.objects.filter(user=request.user, author=author).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['PUT'], url_path='me/avatar')
    def load_avatar(self, request, pk=None):
        """Эндпоинт для добавления аватара"""

        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'avatar': request.build_absolute_uri(user.avatar.url)},
            status=status.HTTP_200_OK,
        )
    @load_avatar.mapping.delete
    def delete_avatar(self, request, pk=None):
        """Эндпоинт для удаления аватара"""
        request.user.avatar.delete(save=True)
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
            self.get_serializer(
                self.paginate_queryset(subscribed_users),
                many=True,
                context={'request': request},
            ).data
        )


class RecipeViewSet(ModelViewSet):
    """ViewSet для модели Рецепт"""

    queryset = Recipe.objects.all()
    permission_classes = [CustomPermission]
    pagination_class = RecipeCustomPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        """Назначение сериализаторов для методов."""

        if self.action == 'favorite':
            return FavoriteSerializer
        elif self.action == 'shopping_cart':
            return ShoppingCartSerializer
        elif self.action in SAFE_METHODS:
            return RecipeSerializer
        else:
            return RecipeCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=['POST'],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        """Эндпоинт для добавления в избранные рецепты."""

        recipe = self.get_object()

        serializer = self.get_serializer(
            data={'recipe': recipe.id},
            context={
                'request': request,
                'recipe': recipe,
            }
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
    @favorite.mapping.delete
    def favorite_delete(self, request, pk=None):
        recipe = self.get_object()
        Favorite.objects.filter(user=request.user, recipe=recipe).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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

    @action(detail=True, methods=['POST'])
    def shopping_cart(self, request, pk=None):
        """Эндпоинт для добавления рецепта
        в список покупок.
        """

        recipe = get_object_or_404(Recipe, pk=pk)

        serializer = self.get_serializer(
            data={
                'recipe': recipe.id,
                },
            context={
                'request': request,
                'recipe': recipe,
                },
            )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            )
    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        """Удаление рецепта из корзины покупок."""

        recipe = get_object_or_404(Recipe, pk=pk)
        ShoppingCart.objects.filter(
            user=request.user,
            recipe=recipe,
        ).delete()
        return Response(
            status=status.HTTP_204_NO_CONTENT,
            )


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
