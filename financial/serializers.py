from rest_framework import serializers
from .models import *

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'

class GLBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = GLBreakdown
        fields = '__all__'

class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'


class MonthlyRevenueBilledSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyRevenueBilled
        fields = '__all__'


