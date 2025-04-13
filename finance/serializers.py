"""
finance/serializers.py

Defines serializers for the finance models to convert model instances to/from JSON.
Also includes simplified list serializers for ExpenseRecord and IncomeRecord.
"""

from rest_framework import serializers
from .models import ExpenseCategory, IncomeCategory, ExpenseRecord, IncomeRecord, Profitability
from herd.serializers import BuffaloListSerializer  # Serializer to represent Buffalo details succinctly

# ---------------- Expense Category Serializer ----------------
class ExpenseCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for ExpenseCategory.
    Uses all fields of the model.
    """
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


# ---------------- Income Category Serializer ----------------
class IncomeCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for IncomeCategory.
    """
    class Meta:
        model = IncomeCategory
        fields = '__all__'


# ---------------- Expense Record List Serializer ----------------
class ExpenseRecordListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing ExpenseRecord data.
    Includes a read-only category name field.
    """
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = ExpenseRecord
        # Use expense_id as identifier for clarity.
        fields = ['expense_id', 'date', 'category', 'category_name', 'description', 'amount', 'supplier_vendor']


# ---------------- Full Expense Record Serializer ----------------
class ExpenseRecordSerializer(serializers.ModelSerializer):
    """
    Full serializer for ExpenseRecord details.
    Includes additional details from related Buffalo using BuffaloListSerializer.
    """
    category_name = serializers.ReadOnlyField(source='category.name')
    related_buffalo_info = BuffaloListSerializer(source='related_buffalo', read_only=True)

    class Meta:
        model = ExpenseRecord
        fields = '__all__'


# ---------------- Income Record List Serializer ----------------
class IncomeRecordListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing IncomeRecord data.
    """
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = IncomeRecord
        fields = ['income_id', 'date', 'category', 'category_name', 'description', 'total_amount', 'customer']


# ---------------- Full Income Record Serializer ----------------
class IncomeRecordSerializer(serializers.ModelSerializer):
    """
    Full serializer for IncomeRecord details.
    Includes related Buffalo information.
    """
    category_name = serializers.ReadOnlyField(source='category.name')
    related_buffalo_info = BuffaloListSerializer(source='related_buffalo', read_only=True)

    class Meta:
        model = IncomeRecord
        fields = '__all__'


# ---------------- Profitability Serializer ----------------
class ProfitabilitySerializer(serializers.ModelSerializer):
    """
    Serializer for Profitability model.
    Adds a method field to return the month name.
    """
    month_name = serializers.SerializerMethodField()

    class Meta:
        model = Profitability
        fields = '__all__'

    def get_month_name(self, obj):
        # Convert numeric month to a full month name.
        month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        return month_names[obj.month - 1]
