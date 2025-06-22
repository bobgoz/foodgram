from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile

from rest_framework.viewsets import ModelViewSet, GenericViewSet, ViewSet
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated, AllowAny, SAFE_METHODS
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

from foodgram.models import Recipe, Tag, Ingredient
from .serializers import (
    RecipeSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    RecipeIngredientInputSerializer,
    UserSerializer
    )

User = get_user_model()


class CustomUserViewSet(UserViewSet):
    """Кастомный ViewSet на основе Djoser UserViewSet."""

    pagination_class = PageNumberPagination
    serializer_class = UserSerializer

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
        pass


class RecipeViewSet(ModelViewSet):
    """ViewSet для модели Рецепт"""

    queryset = Recipe.objects.all()
    permission_classes = [IsAuthenticated]

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
        """Создаёт эндппоинт для скачивания списка покупок."""
        pass


    @action(detail=False, methods=['POST', 'DELETE'])
    def shopping_cart(self, request, pk=None):
        """Создаёт эндпоинт для добавления рецепта
        в список покупок и его удаления.
        """
        pass


class TagViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    """ViewSet для модели Тэг"""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(RetrieveModelMixin, ListModelMixin, GenericViewSet):
    """ViewSet для модели Ингредиент"""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

