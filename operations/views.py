# operations/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.http import JsonResponse
from .models import UtilityReading, UtilityBill, HealthRecord, ScheduledAppointment
from .forms import (
    UtilityReadingForm, UtilityBillForm, HealthRecordForm,
    ScheduledAppointmentForm, CompleteAppointmentForm
)
from datetime import timedelta


# Utility Reading Views
class UtilityReadingListView(LoginRequiredMixin, ListView):
    model = UtilityReading
    template_name = 'operations/utility_reading_list.html'
    context_object_name = 'readings'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by utility type if provided
        utility_type = self.request.GET.get('utility_type')
        if utility_type:
            queryset = queryset.filter(utility_type=utility_type)

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['utility_types'] = UtilityReading.UTILITY_TYPES

        # Add filter parameters to context
        context['utility_type'] = self.request.GET.get('utility_type', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        return context


class UtilityReadingDetailView(LoginRequiredMixin, DetailView):
    model = UtilityReading
    template_name = 'operations/utility_reading_detail.html'
    context_object_name = 'reading'


class UtilityReadingCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = UtilityReading
    form_class = UtilityReadingForm
    template_name = 'operations/utility_reading_form.html'
    permission_required = 'operations.add_utilityreading'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Utility reading added successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Utility Reading'
        context['button_text'] = 'Add Reading'
        return context


class UtilityReadingUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = UtilityReading
    form_class = UtilityReadingForm
    template_name = 'operations/utility_reading_form.html'
    permission_required = 'operations.change_utilityreading'

    def form_valid(self, form):
        messages.success(self.request, 'Utility reading updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Utility Reading'
        context['button_text'] = 'Update Reading'
        return context


class UtilityReadingDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = UtilityReading
    template_name = 'operations/utility_reading_confirm_delete.html'
    context_object_name = 'reading'
    success_url = reverse_lazy('operations:utility_reading_list')
    permission_required = 'operations.delete_utilityreading'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Utility reading deleted successfully.')
        return super().delete(request, *args, **kwargs)


# Utility Bill Views
class UtilityBillListView(LoginRequiredMixin, ListView):
    model = UtilityBill
    template_name = 'operations/utility_bill_list.html'
    context_object_name = 'bills'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by utility type if provided
        utility_type = self.request.GET.get('utility_type')
        if utility_type:
            queryset = queryset.filter(utility_type=utility_type)

        # Filter by payment status if provided
        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(billing_period_end__gte=start_date)
        if end_date:
            queryset = queryset.filter(billing_period_end__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['utility_types'] = UtilityBill.UTILITY_TYPES
        context['payment_statuses'] = UtilityBill.PAYMENT_STATUS

        # Add filter parameters to context
        context['utility_type'] = self.request.GET.get('utility_type', '')
        context['payment_status'] = self.request.GET.get('payment_status', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        # Add summary data
        bills = self.get_queryset()
        context['total_amount'] = bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        context['unpaid_amount'] = bills.filter(payment_status='unpaid').aggregate(Sum('total_amount'))[
                                       'total_amount__sum'] or 0
        context['overdue_amount'] = bills.filter(payment_status='overdue').aggregate(Sum('total_amount'))[
                                        'total_amount__sum'] or 0

        return context


class UtilityBillDetailView(LoginRequiredMixin, DetailView):
    model = UtilityBill
    template_name = 'operations/utility_bill_detail.html'
    context_object_name = 'bill'


class UtilityBillCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = UtilityBill
    form_class = UtilityBillForm
    template_name = 'operations/utility_bill_form.html'
    permission_required = 'operations.add_utilitybill'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Utility bill added successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Utility Bill'
        context['button_text'] = 'Add Bill'
        return context


class UtilityBillUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = UtilityBill
    form_class = UtilityBillForm
    template_name = 'operations/utility_bill_form.html'
    permission_required = 'operations.change_utilitybill'

    def form_valid(self, form):
        messages.success(self.request, 'Utility bill updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Utility Bill'
        context['button_text'] = 'Update Bill'
        return context


class UtilityBillDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = UtilityBill
    template_name = 'operations/utility_bill_confirm_delete.html'
    context_object_name = 'bill'
    success_url = reverse_lazy('operations:utility_bill_list')
    permission_required = 'operations.delete_utilitybill'

    def delete(self, request, *args, **kwargs):
        bill = self.get_object()
        # If there's a related expense record, delete it too
        if bill.related_expense:
            bill.related_expense.delete()

        messages.success(request, 'Utility bill deleted successfully.')
        return super().delete(request, *args, **kwargs)


class UtilityBillMarkAsPaidView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'operations.change_utilitybill'

    def post(self, request, pk):
        bill = get_object_or_404(UtilityBill, pk=pk)
        bill.payment_status = 'paid'
        bill.paid_date = timezone.now().date()
        bill.save()

        messages.success(request, f'Bill {bill.invoice_number or bill.pk} marked as paid.')
        return redirect('operations:utility_bill_detail', pk=bill.pk)


# Health Record Views
class HealthRecordListView(LoginRequiredMixin, ListView):
    model = HealthRecord
    template_name = 'operations/health_record_list.html'
    context_object_name = 'records'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by buffalo if provided
        buffalo_id = self.request.GET.get('buffalo')
        if buffalo_id:
            queryset = queryset.filter(buffalo_id=buffalo_id)

        # Filter by record type if provided
        record_type = self.request.GET.get('record_type')
        if record_type:
            queryset = queryset.filter(record_type=record_type)

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['record_types'] = HealthRecord.RECORD_TYPES

        # Add filter parameters to context
        context['buffalo_id'] = self.request.GET.get('buffalo', '')
        context['record_type'] = self.request.GET.get('record_type', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        # Add summary data
        records = self.get_queryset()
        context['total_cost'] = records.aggregate(Sum('total_cost'))['total_cost__sum'] or 0

        try:
            # Try to import Buffalo model
            from herd.models import Buffalo
            context['buffaloes'] = Buffalo.objects.filter(is_active=True)
        except (ImportError, Exception):
            context['buffaloes'] = []

        return context


class HealthRecordDetailView(LoginRequiredMixin, DetailView):
    model = HealthRecord
    template_name = 'operations/health_record_detail.html'
    context_object_name = 'record'


class HealthRecordCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = HealthRecord
    form_class = HealthRecordForm
    template_name = 'operations/health_record_form.html'
    permission_required = 'operations.add_healthrecord'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Health record added successfully.')

        response = super().form_valid(form)

        # Check if there's a scheduled appointment to link
        appointment_id = self.request.GET.get('appointment_id')
        if appointment_id:
            try:
                appointment = ScheduledAppointment.objects.get(pk=appointment_id)
                appointment.related_health_record = form.instance
                appointment.status = 'completed'
                appointment.save()
                messages.info(self.request, f'Appointment {appointment.pk} marked as completed.')
            except ScheduledAppointment.DoesNotExist:
                pass

        # Check if follow-up appointment should be created
        if form.cleaned_data.get('follow_up_date'):
            follow_up_date = form.cleaned_data.get('follow_up_date')
            buffalo = form.cleaned_data.get('buffalo')
            record_type = form.cleaned_data.get('record_type')

            # Create a follow-up appointment
            ScheduledAppointment.objects.create(
                buffalo=buffalo,
                appointment_type='checkup' if record_type == 'treatment' else record_type,
                scheduled_date=follow_up_date,
                description=f"Follow-up for {form.instance.description}",
                vet_name=form.cleaned_data.get('vet_name'),
                status='scheduled',
                notes=f"Follow-up appointment for health record #{form.instance.pk}",
                created_by=self.request.user
            )
            messages.info(self.request, f'Follow-up appointment scheduled for {follow_up_date}.')

        return response

    def get_initial(self):
        initial = super().get_initial()

        # Pre-fill buffalo if provided in URL
        buffalo_id = self.request.GET.get('buffalo_id')
        if buffalo_id:
            initial['buffalo'] = buffalo_id

        # Pre-fill from appointment if creating from appointment
        appointment_id = self.request.GET.get('appointment_id')
        if appointment_id:
            try:
                appointment = ScheduledAppointment.objects.get(pk=appointment_id)
                initial['buffalo'] = appointment.buffalo
                initial['record_type'] = appointment.appointment_type
                initial['description'] = appointment.description
                initial['vet_name'] = appointment.vet_name
                initial['date'] = appointment.scheduled_date
                initial['notes'] = appointment.notes
            except ScheduledAppointment.DoesNotExist:
                pass

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Health Record'
        context['button_text'] = 'Add Record'

        # Add appointment context if creating from appointment
        appointment_id = self.request.GET.get('appointment_id')
        if appointment_id:
            try:
                appointment = ScheduledAppointment.objects.get(pk=appointment_id)
                context['appointment'] = appointment
                context['title'] = 'Complete Appointment'
            except ScheduledAppointment.DoesNotExist:
                pass

        return context


class HealthRecordUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = HealthRecord
    form_class = HealthRecordForm
    template_name = 'operations/health_record_form.html'
    permission_required = 'operations.change_healthrecord'

    def form_valid(self, form):
        messages.success(self.request, 'Health record updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Health Record'
        context['button_text'] = 'Update Record'
        return context


class HealthRecordDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = HealthRecord
    template_name = 'operations/health_record_confirm_delete.html'
    context_object_name = 'record'
    success_url = reverse_lazy('operations:health_record_list')
    permission_required = 'operations.delete_healthrecord'

    def delete(self, request, *args, **kwargs):
        health_record = self.get_object()

        # If there's a related expense record, delete it too
        if health_record.related_expense:
            health_record.related_expense.delete()

        # If there's a related appointment, update its status
        try:
            appointment = ScheduledAppointment.objects.get(related_health_record=health_record)
            appointment.related_health_record = None
            appointment.status = 'scheduled'
            appointment.save()
        except ScheduledAppointment.DoesNotExist:
            pass

        messages.success(request, 'Health record deleted successfully.')
        return super().delete(request, *args, **kwargs)


# Scheduled Appointment Views
class AppointmentListView(LoginRequiredMixin, ListView):
    model = ScheduledAppointment
    template_name = 'operations/appointment_list.html'
    context_object_name = 'appointments'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filter by buffalo if provided
        buffalo_id = self.request.GET.get('buffalo')
        if buffalo_id:
            queryset = queryset.filter(buffalo_id=buffalo_id)

        # Filter by appointment type if provided
        appointment_type = self.request.GET.get('appointment_type')
        if appointment_type:
            queryset = queryset.filter(appointment_type=appointment_type)

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if start_date:
            queryset = queryset.filter(scheduled_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_date__lte=end_date)

        # Filter upcoming appointments if requested
        if self.request.GET.get('upcoming') == 'true':
            queryset = queryset.filter(
                scheduled_date__gte=timezone.now().date(),
                status='scheduled'
            )

        # Filter overdue appointments if requested
        if self.request.GET.get('overdue') == 'true':
            queryset = queryset.filter(
                scheduled_date__lt=timezone.now().date(),
                status='scheduled'
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['appointment_types'] = ScheduledAppointment.APPOINTMENT_TYPES
        context['status_choices'] = ScheduledAppointment.STATUS_CHOICES

        # Add filter parameters to context
        context['buffalo_id'] = self.request.GET.get('buffalo', '')
        context['appointment_type'] = self.request.GET.get('appointment_type', '')
        context['status'] = self.request.GET.get('status', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['upcoming'] = self.request.GET.get('upcoming', '')
        context['overdue'] = self.request.GET.get('overdue', '')

        # Add counts for quick navigation
        context['upcoming_count'] = ScheduledAppointment.objects.filter(
            scheduled_date__gte=timezone.now().date(),
            status='scheduled'
        ).count()

        context['overdue_count'] = ScheduledAppointment.objects.filter(
            scheduled_date__lt=timezone.now().date(),
            status='scheduled'
        ).count()

        context['today_count'] = ScheduledAppointment.objects.filter(
            scheduled_date=timezone.now().date(),
            status='scheduled'
        ).count()

        try:
            # Try to import Buffalo model
            from herd.models import Buffalo
            context['buffaloes'] = Buffalo.objects.filter(is_active=True)
        except (ImportError, Exception):
            context['buffaloes'] = []

        return context


class AppointmentDetailView(LoginRequiredMixin, DetailView):
    model = ScheduledAppointment
    template_name = 'operations/appointment_detail.html'
    context_object_name = 'appointment'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add CompleteAppointmentForm for quick completion
        if self.object.status == 'scheduled':
            context['complete_form'] = CompleteAppointmentForm(initial={
                'record_type': self.object.appointment_type,
                'description': self.object.description,
                'vet_name': self.object.vet_name,
                'notes': self.object.notes
            })

        return context


class AppointmentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ScheduledAppointment
    form_class = ScheduledAppointmentForm
    template_name = 'operations/appointment_form.html'
    permission_required = 'operations.add_scheduledappointment'

    def form_valid(self, form):
        form.instance.created_by = self.request.user

        # Show warning if scheduled date is in the past
        if hasattr(form, 'warnings'):
            for warning in form.warnings:
                messages.warning(self.request, warning)

        messages.success(self.request, 'Appointment scheduled successfully.')
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()

        # Pre-fill buffalo if provided in URL
        buffalo_id = self.request.GET.get('buffalo_id')
        if buffalo_id:
            initial['buffalo'] = buffalo_id

        # Set scheduled date to tomorrow by default
        tomorrow = timezone.now().date() + timedelta(days=1)
        initial['scheduled_date'] = tomorrow

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Schedule Appointment'
        context['button_text'] = 'Schedule'
        return context


class AppointmentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ScheduledAppointment
    form_class = ScheduledAppointmentForm
    template_name = 'operations/appointment_form.html'
    permission_required = 'operations.change_scheduledappointment'

    def form_valid(self, form):
        # Show warning if scheduled date is in the past
        if hasattr(form, 'warnings'):
            for warning in form.warnings:
                messages.warning(self.request, warning)

        messages.success(self.request, 'Appointment updated successfully.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Appointment'
        context['button_text'] = 'Update'
        return context


class AppointmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ScheduledAppointment
    template_name = 'operations/appointment_confirm_delete.html'
    context_object_name = 'appointment'
    success_url = reverse_lazy('operations:appointment_list')
    permission_required = 'operations.delete_scheduledappointment'

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Appointment deleted successfully.')
        return super().delete(request, *args, **kwargs)


class AppointmentCompleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = ['operations.change_scheduledappointment', 'operations.add_healthrecord']

    def post(self, request, pk):
        appointment = get_object_or_404(ScheduledAppointment, pk=pk)
        form = CompleteAppointmentForm(request.POST)

        if form.is_valid():
            # Create a new health record
            health_record = HealthRecord.objects.create(
                buffalo=appointment.buffalo,
                date=timezone.now().date(),
                record_type=form.cleaned_data['record_type'],
                description=form.cleaned_data['description'],
                vet_name=form.cleaned_data['vet_name'] or appointment.vet_name,
                medication_used=form.cleaned_data['medication_used'],
                medication_cost=form.cleaned_data['medication_cost'] or 0,
                service_cost=form.cleaned_data['service_cost'] or 0,
                total_cost=(form.cleaned_data['medication_cost'] or 0) + (form.cleaned_data['service_cost'] or 0),
                follow_up_date=form.cleaned_data['follow_up_date'],
                notes=form.cleaned_data['notes'] or appointment.notes,
                created_by=request.user
            )

            # Update the appointment
            appointment.status = 'completed'
            appointment.related_health_record = health_record
            appointment.save()

            # Create follow-up appointment if requested
            if form.cleaned_data['follow_up_date']:
                follow_up = ScheduledAppointment.objects.create(
                    buffalo=appointment.buffalo,
                    appointment_type='checkup',
                    scheduled_date=form.cleaned_data['follow_up_date'],
                    description=f"Follow-up for {form.cleaned_data['description']}",
                    vet_name=form.cleaned_data['vet_name'] or appointment.vet_name,
                    status='scheduled',
                    notes=f"Follow-up for appointment #{appointment.pk}",
                    created_by=request.user
                )
                messages.info(request, f'Follow-up appointment scheduled for {follow_up.scheduled_date}.')

            messages.success(request, 'Appointment completed and health record created successfully.')
            return redirect('operations:health_record_detail', pk=health_record.pk)

        # If form is invalid, go back to appointment detail with errors
        messages.error(request, 'There was an error completing the appointment. Please check the form.')
        return redirect('operations:appointment_detail', pk=pk)


# API Views for Dashboard Integration
def get_upcoming_appointments(request):
    """API endpoint to get upcoming appointments for dashboard widgets."""
    days = int(request.GET.get('days', 7))
    end_date = timezone.now().date() + timedelta(days=days)

    appointments = ScheduledAppointment.objects.filter(
        scheduled_date__gte=timezone.now().date(),
        scheduled_date__lte=end_date,
        status='scheduled'
    ).select_related('buffalo').order_by('scheduled_date')

    appointment_data = [
        {
            'id': appointment.pk,
            'buffalo_name': appointment.buffalo.name if appointment.buffalo else 'Herd',
            'buffalo_id': appointment.buffalo.pk if appointment.buffalo else None,
            'type': appointment.get_appointment_type_display(),
            'date': appointment.scheduled_date.strftime('%Y-%m-%d'),
            'description': appointment.description,
            'vet_name': appointment.vet_name,
            'days_until': appointment.days_until_appointment,
            'url': reverse('operations:appointment_detail', kwargs={'pk': appointment.pk})
        }
        for appointment in appointments[:10]  # Limit to 10 records
    ]

    return JsonResponse({
        'appointments': appointment_data,
        'total_count': appointments.count()
    })


def get_overdue_appointments(request):
    """API endpoint to get overdue appointments for dashboard widgets and alerts."""
    appointments = ScheduledAppointment.objects.filter(
        scheduled_date__lt=timezone.now().date(),
        status='scheduled'
    ).select_related('buffalo').order_by('scheduled_date')

    appointment_data = [
        {
            'id': appointment.pk,
            'buffalo_name': appointment.buffalo.name if appointment.buffalo else 'Herd',
            'buffalo_id': appointment.buffalo.pk if appointment.buffalo else None,
            'type': appointment.get_appointment_type_display(),
            'date': appointment.scheduled_date.strftime('%Y-%m-%d'),
            'description': appointment.description,
            'vet_name': appointment.vet_name,
            'days_overdue': (timezone.now().date() - appointment.scheduled_date).days,
            'url': reverse('operations:appointment_detail', kwargs={'pk': appointment.pk})
        }
        for appointment in appointments[:10]  # Limit to 10 records
    ]

    return JsonResponse({
        'appointments': appointment_data,
        'total_count': appointments.count()
    })


def get_utility_consumption(request):
    """API endpoint to get utility consumption data for charting."""
    utility_type = request.GET.get('utility_type', 'electricity')
    months = int(request.GET.get('months', 12))

    # Calculate the date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30 * months)

    # Get utility bills for the selected type in the date range
    bills = UtilityBill.objects.filter(
        utility_type=utility_type,
        billing_period_end__gte=start_date,
        billing_period_end__lte=end_date
    ).order_by('billing_period_end')

    # Prepare data for chart
    chart_data = {
        'labels': [],
        'consumption': [],
        'cost': []
    }

    for bill in bills:
        chart_data['labels'].append(bill.billing_period_end.strftime('%b %Y'))
        chart_data['consumption'].append(float(bill.consumption))
        chart_data['cost'].append(float(bill.total_amount))

    return JsonResponse(chart_data)


def get_health_expenses(request):
    """API endpoint to get health expense data for charting."""
    months = int(request.GET.get('months', 12))

    # Calculate the date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30 * months)

    # Get health records in the date range
    health_records = HealthRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )

    # Group by record type
    record_types = {}
    for record_type, display_name in HealthRecord.RECORD_TYPES:
        record_types[record_type] = {
            'name': display_name,
            'count': health_records.filter(record_type=record_type).count(),
            'total_cost': float(
                health_records.filter(record_type=record_type).aggregate(Sum('total_cost'))['total_cost__sum'] or 0)
        }

    # Prepare data for chart
    chart_data = {
        'types': list(record_types.keys()),
        'names': [data['name'] for data in record_types.values()],
        'counts': [data['count'] for data in record_types.values()],
        'costs': [data['total_cost'] for data in record_types.values()],
        'total_cost': float(health_records.aggregate(Sum('total_cost'))['total_cost__sum'] or 0),
        'total_count': health_records.count()
    }

    return JsonResponse(chart_data)