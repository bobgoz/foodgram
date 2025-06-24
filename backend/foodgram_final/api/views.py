from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import HttpResponse

from django.db.models import Sum
from django.db import models



from rest_framework.viewsets import ModelViewSet, GenericViewSet, ViewSet
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
from rest_framework import pagination
from rest_framework.response import Response
from rest_framework import status
from rest_framework.mixins import (ListModelMixin,
                                   RetrieveModelMixin, 
                                   CreateModelMixin)
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FileUploadParser

import base64
import filetype


from djoser.views import UserViewSet

from foodgram.models import (
    Recipe,
    Tag,
    Ingredient,
    ShoppingCart,
    Subscription,
    RecipeIngredient)

from .serializers import (
    RecipeSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    RecipeIngredientInputSerializer,
    UserSerializer,
    SubscriptionSerializer,
    )

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    """Кастомный ViewSet на основе Djoser UserViewSet."""

    pagination_class = PageNumberPagination
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.prefetch_related('following').all()

    @action(detail=False, methods=['POST', 'DELETE'])
    def subscribe(self, request, pk=None):
        """Создаёт эндпоинт для подписки на пользователей и отписки."""
        pass

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
                if kind is None or kind.mime not in ['image/jpeg', 'image/png', 'image/gif']:
                    return Response(
                        {"error": "Invalid image format. Only JPEG, PNG, and GIF are allowed."},
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


    @action(detail=False, methods=['GET'])
    def subscriptions(self, request, pk=None):
        """Создаёт эндпоинт, который возвращает
        список пользователей на которых подписан
        текущий пользователь.
        """
        
        # Получаем подписки текущего пользователя
        subscriptions = Subscription.objects.filter(user=request.user)
        
        # Оптимизация запросов
        authors = User.objects.filter(
            id__in=subscriptions.values('author')
        ).prefetch_related(
            models.Prefetch('recipes', queryset=Recipe.objects.all()[:3])  # последние 3 рецепта
        )
        
        # Пагинация
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = SubscriptionSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        
        serializer = SubscriptionSerializer(
            authors,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class RecipeViewSet(ModelViewSet):
    """ViewSet для модели Рецепт"""

    queryset = Recipe.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = pagination.LimitOffsetPagination
    page_size = 1

    def get_serializer_class(self):
        if self.action in SAFE_METHODS:
            return RecipeSerializer
        return RecipeCreateUpdateSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=False, methods=['GET'], url_path='get-link')
    def get_link(self, request, pk=None):
        """Создает ндпоинт get-link для 
        получения короткой ссылки на рецепт.
        """
        pass

    @action(detail=False, methods=['GET'])
    def download_shopping_cart(self, request, pk=None):
        """Генерирует PDF списком покупок."""
        
        # данные для PDF
        shopping_list = self._generate_shopping_list(request.user)
        
        # Создание PDF
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)

        # Настройки документа
        p.setFont('Helvetica', 12)
        y_position = 750
        
        # Заголовок
        p.drawString(100, y_position, 'Список покупок')
        y_position -= 30

        # Содержимое
        for item in shopping_list:
            p.drawString(100, y_position, f"- {item['ingredient__name']} ({item['amount']} {item['ingredient__measurement_unit']})")
            y_position -= 20
            if y_position < 50:  # Если конец страницы
                p.showPage()
                y_position = 750
                p.setFont("Helvetica", 12)

        p.save()

        # Возвращение PDF как ответ
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="shopping_list.pdf"'
        return response

    def _generateshopping_list(self, user):
        """Генерирует список ингредиентв."""

        return (
            RecipeIngredient.objects
            .filter(recipe__shopping_carts__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total=Sum('amount'))
            .order_by('ingredient__name')
        )

    @action(detail=True, methods=['POST', 'DELETE'])
    def shopping_cart(self, request, pk=None):
        """Создаёт эндпоинт для добавления рецепта
        в список покупок и его удаления.
        """

        recipe = get_object_or_404(Recipe, id=pk)

        if request.method == 'POST':
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
            cart_item = get_object_or_404(
                ShoppingCart, user=request.user, recipe=recipe)
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    """ViewSet для модели Тэг"""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    """ViewSet для модели Ингредиент"""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer


class SubscriptionViewSet(ModelViewSet):
    """ViewSet для модели Подписки."""
    
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
    

