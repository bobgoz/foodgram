from rest_framework.pagination import PageNumberPagination


class LimitPageNumberPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'limit'


class RecipeCustomPagination(PageNumberPagination):
    """Кастомная пагинация для эндпоинта /api/recipes/ """

    page_size_query_param = 'limit'
    page_size = 10
    max_page_size = 100
