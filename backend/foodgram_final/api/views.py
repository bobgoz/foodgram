from io import BytesIO

from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect
from django.conf import settings
from django.http import HttpResponse
from django.db.models import Sum, Count
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
from djoser.views import UserViewSet

from foodgram.models import (
    Recipe,
    Tag,
    Ingredient,
    Subscription,
    RecipeIngredient,
    Token,
)

from .serializers import (
    RecipeSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    UserSerializer,
    SubscriptionCreateSerializer,
    SubscriptionDeleteSerializer,
    FavoriteCreateSerializer,
    FavoriteDeleteSerializer,
    ShoppingCartSerializer,
    ShoppingCartDeleteSerializer,
    AvatarSerializer,
    SubscriptionShowSerializer,
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
    serializer_class = UserSerializer
    permission_classes = (CustomPermission,)
    filter_backends = (DjangoFilterBackend,)

    def get_serializer_class(self):
        """Назначение сериализаторов для методов."""
        if self.action == 'subscribe':
            return SubscriptionCreateSerializer
        if self.action == 'subscribe_delete':
            return SubscriptionDeleteSerializer
        if self.action == 'load_avatar':
            return AvatarSerializer
        if self.action == 'subscriptions':
            return SubscriptionShowSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=['POST'])
    def subscribe(self, request, id=None):
        """Создаёт эндпоинт для подписки на пользователей и отписки."""

        serializer = self.get_serializer(
            data={
                'author': id,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(raise_exception=True)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def subscribe_delete(self, request, id=None):
        """Удаление подписки"""

        serializer = self.get_serializer(
            data={
                'author': id,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.delete()
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
            {'avatar': request.build_absolute_uri(request.user.avatar.url)},
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

        queryset = User.objects.filter(
            following__user=request.user,
        ).annotate(
            recipes_count=Count('recipes'),).order_by(
                '-following__created_at'
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(
            page, many=True,
        )
        return self.get_paginated_response(serializer.data)


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
            return FavoriteCreateSerializer
        if self.action == 'favorite_delete':
            return FavoriteDeleteSerializer
        if self.action == 'shopping_cart':
            return ShoppingCartSerializer
        if self.action == 'delete_shopping_cart':
            return ShoppingCartDeleteSerializer
        if self.action in SAFE_METHODS:
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

        serializer = self.get_serializer(
            data={
                'recipe': pk,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @favorite.mapping.delete
    def favorite_delete(self, request, pk=None):
        """Удаление из избранных."""

        serializer = self.get_serializer(
            data={
                'recipe': pk,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.delete()
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

        serializer = self.get_serializer(
            data={
                'recipe': pk,
                'user': request.user.id,
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

        serializer = self.get_serializer(
            data={
                'recipe': pk,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.delete()
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
    serializer_class = RecipeCreateUpdateSerializer
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
