"""
tests.py

This file contains production-grade tests for the finance app in the Dairy ERP system.
Tests cover:
  • Model behavior and formulas (e.g. auto-calculations)
  • Signal functionality (e.g. updating Buffalo cumulative cost)
  • Views: HTTP requests, form submissions, redirections, and context data
  • API endpoints using Django REST Framework’s APIClient

For a production-grade system, these tests provide comprehensive coverage and validation of core business logic.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
import json

# Import APIClient from DRF for API tests.
from rest_framework.test import APIClient

# Import models from the finance app and any required models from other apps.
from .models import ExpenseCategory, IncomeCategory, ExpenseRecord, IncomeRecord, Profitability, Loan, LoanPayment
from herd.models import Buffalo
from configuration.models import GlobalSettings

# -------------------------
# Model & Business Logic Tests
# -------------------------
class FinanceModelsTest(TestCase):
    def setUp(self):
        # Create a test expense category and income category.
        self.expense_cat = ExpenseCategory.objects.create(
            name="Test Expense",
            is_direct_cost=True,
            description="Test Direct Expense"
        )
        self.income_cat = IncomeCategory.objects.create(
            name="Test Income",
            description="Test Income Category"
        )
        # Create a test Buffalo object (simulate an active animal).
        self.buffalo = Buffalo.objects.create(
            name="Buffalo A",
            cumulative_cost=Decimal("0.00")
        )
        # Create a global settings entry with a default milk price.
        self.settings = GlobalSettings.objects.create(
            default_milk_price_per_litre=Decimal("2.50")
        )

    def test_income_record_auto_calculation(self):
        """
        Test that an IncomeRecord calculates total_amount automatically
        when both quantity and unit_price are provided.
        """
        income = IncomeRecord.objects.create(
            date=timezone.now().date(),
            category=self.income_cat,
            description="Milk sale test",
            quantity=Decimal("10.00"),
            unit_price=Decimal("3.00"),
            total_amount=Decimal("0.00"),  # should be auto-calculated in save()
        )
        income.save()  # Trigger save() logic
        self.assertEqual(income.total_amount, Decimal("30.00"), "Total amount should equal 10 * 3 = 30.00")

    def test_expense_record_updates_buffalo_cumulative_cost(self):
        """
        Test that saving an ExpenseRecord with a related buffalo
        updates the buffalo's cumulative_cost via the signal.
        """
        initial_cost = self.buffalo.cumulative_cost
        expense = ExpenseRecord.objects.create(
            date=timezone.now().date(),
            category=self.expense_cat,
            description="Feed cost",
            amount=Decimal("100.00"),
            related_buffalo=self.buffalo
        )
        # Force a refresh from the database
        self.buffalo.refresh_from_db()
        self.assertEqual(self.buffalo.cumulative_cost, initial_cost + Decimal("100.00"),
                         "Buffalo cumulative_cost should be updated by expense amount.")

    def test_profitability_record_str(self):
        """
        Test the string representation of a Profitability record.
        """
        record = Profitability.objects.create(
            year=2025,
            month=4,
            total_income=Decimal("1000.00"),
            direct_costs=Decimal("300.00"),
            indirect_costs=Decimal("200.00"),
            gross_profit=Decimal("700.00"),
            net_profit=Decimal("500.00"),
            roi=Decimal("5.00"),
            cash_surplus=Decimal("100.00")
        )
        expected = "4/2025 Profitability"
        self.assertEqual(str(record), expected, "Profitability __str__ should return 'month/year Profitability'.")

# -------------------------
# Views Tests
# -------------------------
class FinanceViewsTest(TestCase):
    def setUp(self):
        # Set up a test client.
        self.client = Client()
        # Create necessary objects.
        self.expense_cat = ExpenseCategory.objects.create(
            name="Test Expense",
            is_direct_cost=True,
            description="Expense for testing"
        )
        self.income_cat = IncomeCategory.objects.create(
            name="Test Income",
            description="Income for testing"
        )
        self.buffalo = Buffalo.objects.create(
            name="Buffalo Test",
            cumulative_cost=Decimal("0.00")
        )
        # Create a user and log in
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username="testuser", password="testpassword")
        self.client.login(username="testuser", password="testpassword")

    def test_expense_category_list_view(self):
        """
        Test that the expense_category_list view returns the correct template and context.
        """
        url = reverse('finance:expense_category_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dairy_erp/finance/expense_category_list.html')
        self.assertIn('categories', response.context)

    def test_income_add_view_post(self):
        """
        Test creating an income record via the income_add view.
        """
        url = reverse('finance:income_add')
        # Posting minimal required fields for IncomeRecordForm
        data = {
            'date': timezone.now().date().isoformat(),
            'category': self.income_cat.id,
            'description': 'Test Income View',
            'quantity': '10.00',
            'unit_price': '2.00',
            'total_amount': '0.00',  # Should be auto-calculated
            'customer': 'Test Customer'
        }
        response = self.client.post(url, data)
        # On successful creation, should redirect to income_list.
        self.assertEqual(response.status_code, 302)
        # Check that record exists.
        self.assertTrue(IncomeRecord.objects.filter(description="Test Income View").exists())

    def test_export_income_view(self):
        """
        Test that the export_income view returns a CSV file.
        """
        # Create a dummy income record.
        IncomeRecord.objects.create(
            date=timezone.now().date(),
            category=self.income_cat,
            description="CSV Export Test",
            quantity=Decimal("5.00"),
            unit_price=Decimal("3.00"),
            total_amount=Decimal("15.00")
        )
        url = reverse('finance:export_income')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn("CSV Export Test", content)

# -------------------------
# API Endpoints Tests (using DRF APIClient)
# -------------------------
class FinanceAPITest(TestCase):
    def setUp(self):
        # Initialize the DRF APIClient and create a user.
        self.client = APIClient()
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username="apiuser", password="apipassword")
        self.client.login(username="apiuser", password="apipassword")
        # Create sample categories.
        self.expense_cat = ExpenseCategory.objects.create(
            name="API Expense",
            is_direct_cost=True,
            description="Expense for API testing"
        )
        self.income_cat = IncomeCategory.objects.create(
            name="API Income",
            description="Income for API testing"
        )

    def test_api_expense_category_list(self):
        """
        Test API endpoint for listing ExpenseCategory records.
        """
        response = self.client.get("/finance/api/expense-categories/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Expect at least one record.
        self.assertGreaterEqual(len(data), 1)

    def test_api_create_income_record(self):
        """
        Test the API endpoint to create a new IncomeRecord.
        """
        data = {
            "date": timezone.now().date().isoformat(),
            "category": self.income_cat.id,
            "description": "API Created Income",
            "quantity": "20.00",
            "unit_price": "2.50",
            "total_amount": "0.00",  # Let backend calculate this
            "customer": "API Customer"
        }
        response = self.client.post("/finance/api/income/", data, format='json')
        self.assertEqual(response.status_code, 201)
        result = response.json()
        # Check that total_amount is calculated as 20 * 2.50 = 50.00
        self.assertEqual(Decimal(result['total_amount']), Decimal('50.00'))

    def test_api_profitability_filter(self):
        """
        Test API endpoint for filtering Profitability records.
        """
        # Create a sample Profitability record.
        Profitability.objects.create(
            year=2025,
            month=5,
            total_income=Decimal("2000.00"),
            direct_costs=Decimal("500.00"),
            indirect_costs=Decimal("300.00"),
            gross_profit=Decimal("1500.00"),
            net_profit=Decimal("1200.00"),
            roi=Decimal("6.00"),
            cash_surplus=Decimal("100.00")
        )
        response = self.client.get("/finance/api/profitability/?year=2025")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(rec['year'] == 2025 for rec in data))

# -------------------------
# Signal and Integration Tests
# -------------------------
class FinanceIntegrationTest(TestCase):
    def setUp(self):
        # Create necessary objects.
        self.expense_cat = ExpenseCategory.objects.create(
            name="Integration Expense",
            is_direct_cost=True,
            description="Integration Test Expense"
        )
        self.buffalo = Buffalo.objects.create(
            name="Integration Buffalo",
            cumulative_cost=Decimal("0.00")
        )

    def test_signal_updates_cumulative_cost_on_expense_save(self):
        """
        Test that the post_save signal for ExpenseRecord updates the associated Buffalo's cumulative_cost.
        """
        # Initially, cumulative_cost should be 0.
        self.assertEqual(self.buffalo.cumulative_cost, Decimal("0.00"))
        # Create an expense record related to the buffalo.
        ExpenseRecord.objects.create(
            date=date.today(),
            category=self.expense_cat,
            description="Integration Signal Test",
            amount=Decimal("250.00"),
            related_buffalo=self.buffalo
        )
        # Refresh buffalo instance from DB and verify cumulative_cost is updated.
        self.buffalo.refresh_from_db()
        self.assertEqual(self.buffalo.cumulative_cost, Decimal("250.00"))
