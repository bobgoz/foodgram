from rest_framework.serializers import PrimaryKeyRelatedField, ValidationError


class TagPrimaryKeyField(PrimaryKeyRelatedField):
    """Обрабатывает формат {'id': value}"""

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            return ValidationError('Ожидается словарь с полем "id".')
        return super().to_internal_value(data)
