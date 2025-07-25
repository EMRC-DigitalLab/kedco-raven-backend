
from rest_framework import viewsets, status
# hr/views.py
from rest_framework import viewsets
from .models import Department, Role, Staff
from .serializers import DepartmentSerializer, RoleSerializer, StaffSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.views import APIView
from rest_framework.response import Response
from hr.metrics import get_hr_summary
from common.utils.filters import get_month_range_from_request
from django.db.models import Avg, Count, Sum, Q
from datetime import date
from common.models import State
from commercial.models import DailyCollection
from common.utils.filters import get_month_range_from_request
from django.shortcuts import get_object_or_404
from commercial.models import MonthlyCommercialSummary
from rest_framework.decorators import action
from django.db import transaction

from common.models import BusinessDistrict as District
from .models import Staff
from .serializers import StaffSerializer


from datetime import date, datetime
from dateutil.relativedelta import relativedelta # type: ignore

from hr.models import Staff
from common.models import BusinessDistrict
from commercial.models import SalesRepresentative, DailyCollection, MonthlyCommercialSummary
from common.models import State


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'slug']


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    filter_backends = [SearchFilter]
    search_fields = ['title', 'slug', 'department__name']


# class StaffViewSet(viewsets.ModelViewSet):
#     queryset = Staff.objects.all()
#     serializer_class = StaffSerializer
#     filter_backends = [DjangoFilterBackend, SearchFilter]
#     # filterset_fields = [
#     #     'department', 'role', 'state', 'district', 'gender', 'grade', 'is_active'
#     # ]
#     filterset_fields = [
#         'department', 'role', 'state', 'district', 'gender', 'grade',
#     ]
#     search_fields = ['full_name', 'email', 'phone_number']

# class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['department', 'role', 'state', 'district', 'gender', 'grade']
    search_fields = ['full_name', 'email', 'phone_number']

    def resolve_district_slug_to_uuid(self, district_slug):
        """
        Treat incoming 'district' value as the slug (e.g. 'JG-NT'),
        look it up in BusinessDistrict.slug, and return its PK.
        """
        if not district_slug:
            print("🐍 ❌ No district slug provided")
            return None

        slug = district_slug.strip()
        try:
            district = District.objects.get(slug__iexact=slug)
            return district.id
        except District.DoesNotExist:
            print(f"🐍 ❌ District slug '{slug}' not found")
            return None

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        staff_data = request.data.get('staff', [])
        print(f"🐍 Received {len(staff_data)} staff for bulk create")
        if not staff_data:
            return Response({'error': 'No staff data provided'}, status=status.HTTP_400_BAD_REQUEST)

        created, updated, errors = [], [], []
        with transaction.atomic():
            for idx, staff_item in enumerate(staff_data):
                try:
                    slug = staff_item.get('district')
                    pk = self.resolve_district_slug_to_uuid(slug)
                    if not pk:
                        errors.append({'index': idx, 'data': staff_item,
                                       'errors': f"District slug '{slug}' could not be resolved"})
                        continue
                    staff_item['district'] = pk
                    # Normalize hire_date to YYYY-MM-DD
                    if isinstance(staff_item.get('hire_date'), str) and 'T' in staff_item['hire_date']:
                        staff_item['hire_date'] = staff_item['hire_date'].split('T')[0]

                    existing = self.get_queryset().filter(
                        district=pk,
                        full_name=staff_item.get('full_name'),
                        hire_date=staff_item.get('hire_date')
                    ).first()

                    if existing:
                        serializer = self.get_serializer(existing, data=staff_item, partial=True)
                        if serializer.is_valid():
                            serializer.save()
                            updated.append(serializer.data)
                        else:
                            errors.append({'index': idx, 'data': staff_item, 'errors': serializer.errors})
                    else:
                        serializer = self.get_serializer(data=staff_item)
                        if serializer.is_valid():
                            serializer.save()
                            created.append(serializer.data)
                        else:
                            errors.append({'index': idx, 'data': staff_item, 'errors': serializer.errors})
                except Exception as e:
                    print(f"🐍 ❌ Exception at {idx}: {e}")
                    errors.append({'index': idx, 'data': staff_item, 'errors': str(e)})

        response_data = {'created': len(created), 'updated': len(updated), 'errors': len(errors),
                         'created_data': created, 'updated_data': updated}
        if errors:
            response_data['error_details'] = errors
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        staff_data = request.data.get('staff', [])
        print(f"🐍 Received {len(staff_data)} staff for bulk update")
        if not staff_data:
            return Response({'error': 'No staff data provided'}, status=status.HTTP_400_BAD_REQUEST)

        updated, errors = [], []
        with transaction.atomic():
            for idx, staff_item in enumerate(staff_data):
                try:
                    comp = staff_item.get('_composite_key', {})
                    slug = comp.get('district') or staff_item.get('district')
                    pk = self.resolve_district_slug_to_uuid(slug)
                    if not pk:
                        errors.append({'index': idx, 'data': staff_item,
                                       'errors': f"District slug '{slug}' could not be resolved"})
                        continue
                    # Normalize dates
                    if comp and isinstance(comp.get('hire_date'), str) and 'T' in comp['hire_date']:
                        comp['hire_date'] = comp['hire_date'].split('T')[0]
                    if isinstance(staff_item.get('hire_date'), str) and 'T' in staff_item['hire_date']:
                        staff_item['hire_date'] = staff_item['hire_date'].split('T')[0]

                    if comp:
                        existing = self.get_queryset().filter(
                            district=pk,
                            full_name=comp.get('full_name'),
                            hire_date=comp.get('hire_date')
                        ).first()
                        data = {**staff_item, 'district': pk}
                        data.pop('_composite_key', None)
                    else:
                        existing = self.get_queryset().filter(
                            district=pk,
                            full_name=staff_item.get('full_name'),
                            hire_date=staff_item.get('hire_date')
                        ).first()
                        data = {**staff_item, 'district': pk}

                    if not existing:
                        errors.append({'index': idx, 'data': staff_item, 'errors': 'Staff not found for update'})
                        continue

                    serializer = self.get_serializer(existing, data=data, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        updated.append(serializer.data)
                    else:
                        errors.append({'index': idx, 'data': staff_item, 'errors': serializer.errors})
                except Exception as e:
                    print(f"🐍 ❌ Exception at {idx}: {e}")
                    errors.append({'index': idx, 'data': staff_item, 'errors': str(e)})

        response_data = {'updated': len(updated), 'errors': len(errors), 'updated_data': updated}
        if errors:
            response_data['error_details'] = errors
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        staff_data = request.data.get('staff', [])
        print(f"🐍 Received {len(staff_data)} staff for bulk delete")
        if not staff_data:
            return Response({'error': 'No staff data provided'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, errors = 0, []
        with transaction.atomic():
            for idx, staff_item in enumerate(staff_data):
                try:
                    comp = staff_item.get('_composite_key', {})
                    slug = comp.get('district') or staff_item.get('district')
                    pk = self.resolve_district_slug_to_uuid(slug)
                    if not pk:
                        errors.append({'index': idx, 'data': staff_item,
                                       'errors': f"District slug '{slug}' could not be resolved"})
                        continue
                    # Normalize dates
                    if comp and isinstance(comp.get('hire_date'), str) and 'T' in comp['hire_date']:
                        comp['hire_date'] = comp['hire_date'].split('T')[0]
                    if isinstance(staff_item.get('hire_date'), str) and 'T' in staff_item['hire_date']:
                        staff_item['hire_date'] = staff_item['hire_date'].split('T')[0]

                    if comp:
                        existing = self.get_queryset().filter(
                            district=pk,
                            full_name=comp.get('full_name'),
                            hire_date=comp.get('hire_date')
                        ).first()
                    else:
                        existing = self.get_queryset().filter(
                            district=pk,
                            full_name=staff_item.get('full_name'),
                            hire_date=staff_item.get('hire_date')
                        ).first()

                    if existing:
                        existing.delete()
                        deleted += 1
                    else:
                        errors.append({'index': idx, 'data': staff_item, 'errors': 'Staff not found for deletion'})
                except Exception as e:
                    print(f"🐍 ❌ Exception at {idx}: {e}")
                    errors.append({'index': idx, 'data': staff_item, 'errors': str(e)})

        response_data = {'deleted': deleted, 'errors': len(errors)}
        if errors:
            response_data['error_details'] = errors
        return Response(response_data, status=status.HTTP_200_OK)
class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['department', 'role', 'state', 'district', 'gender', 'grade']
    search_fields = ['full_name', 'email', 'phone_number']

    def resolve_district_slug_to_uuid(self, district_slug):
        """
        Treat incoming 'district' value as the slug (e.g. 'JG-NT'),
        look it up in BusinessDistrict.slug, and return its PK.
        """
        if not district_slug:
            print("No district slug provided")
            return None

        slug = district_slug.strip()
        try:
            district = District.objects.get(slug__iexact=slug)
            print(f"District slug '{slug}' resolved to PK: {district.id}")
            return district.id
        except District.DoesNotExist:
            print(f"District slug '{slug}' not found")
            return None

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        staff_data = request.data.get('staff', [])
        print(f"Received {len(staff_data)} staff for bulk create")
        if not staff_data:
            return Response({'error': 'No staff data provided'}, status=status.HTTP_400_BAD_REQUEST)

        created, updated, errors = [], [], []
        with transaction.atomic():
            for idx, staff_item in enumerate(staff_data):
                try:
                    print(f"Processing item {idx}: {staff_item}")
                    
                    # Normalize hire_date to YYYY-MM-DD
                    original_hire_date = staff_item.get('hire_date')
                    if isinstance(staff_item.get('hire_date'), str) and 'T' in staff_item['hire_date']:
                        staff_item['hire_date'] = staff_item['hire_date'].split('T')[0]
                    print(f"Hire date normalized: {original_hire_date} → {staff_item.get('hire_date')}")

                    # Search by district__slug + full_name + hire_date (using district slug through FK)
                    search_criteria = {
                        'district__slug': staff_item.get('district'),
                        'full_name': staff_item.get('full_name'),
                        'hire_date': staff_item.get('hire_date')
                    }
                    print(f"Looking for existing staff with: {search_criteria}")
                    
                    existing = self.get_queryset().filter(**search_criteria).first()
                    print(f"Found existing record: {existing}")
                    
                    # Only resolve district for saving, not for searching
                    slug = staff_item.get('district')
                    pk = self.resolve_district_slug_to_uuid(slug)
                    if not pk:
                        errors.append({'index': idx, 'data': staff_item,
                                       'errors': f"District slug '{slug}' could not be resolved"})
                        continue
                    
                    if existing:
                        print(f"UPDATING existing staff ID: {existing.id}")
                        update_data = {**staff_item, 'district': pk}
                        serializer = self.get_serializer(existing, data=update_data, partial=True)
                        if serializer.is_valid():
                            saved_instance = serializer.save()
                            print(f"Successfully updated staff ID: {saved_instance.id}")
                            updated.append(serializer.data)
                        else:
                            print(f"Update validation failed: {serializer.errors}")
                            errors.append({'index': idx, 'data': staff_item, 'errors': serializer.errors})
                    else:
                        print(f"CREATING new staff record")
                        create_data = {**staff_item, 'district': pk}
                        serializer = self.get_serializer(data=create_data)
                        if serializer.is_valid():
                            saved_instance = serializer.save()
                            print(f"Successfully created staff ID: {saved_instance.id}")
                            created.append(serializer.data)
                        else:
                            print(f"Create validation failed: {serializer.errors}")
                            errors.append({'index': idx, 'data': staff_item, 'errors': serializer.errors})
                except Exception as e:
                    print(f"Exception at {idx}: {e}")
                    import traceback
                    print(f"Full traceback: {traceback.format_exc()}")
                    errors.append({'index': idx, 'data': staff_item, 'errors': str(e)})

        print(f"Final results: Created={len(created)}, Updated={len(updated)}, Errors={len(errors)}")
        response_data = {'created': len(created), 'updated': len(updated), 'errors': len(errors),
                         'created_data': created, 'updated_data': updated}
        if errors:
            response_data['error_details'] = errors
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'])
    def bulk_update(self, request):
        staff_data = request.data.get('staff', [])
        print(f"Received {len(staff_data)} staff for bulk update")
        if not staff_data:
            return Response({'error': 'No staff data provided'}, status=status.HTTP_400_BAD_REQUEST)

        updated, errors = [], []
        with transaction.atomic():
            for idx, staff_item in enumerate(staff_data):
                try:
                    print(f"Processing UPDATE item {idx}: {staff_item}")
                    
                    # Normalize dates
                    comp = staff_item.get('_composite_key', {})
                    if comp and isinstance(comp.get('hire_date'), str) and 'T' in comp['hire_date']:
                        comp['hire_date'] = comp['hire_date'].split('T')[0]
                    if isinstance(staff_item.get('hire_date'), str) and 'T' in staff_item['hire_date']:
                        staff_item['hire_date'] = staff_item['hire_date'].split('T')[0]

                    # Search using district__slug (through FK relationship)
                    if comp:
                        search_criteria = {
                            'district__slug': comp.get('district'),
                            'full_name': comp.get('full_name'),
                            'hire_date': comp.get('hire_date')
                        }
                        print(f"UPDATE: Looking for existing staff with composite key: {search_criteria}")
                        existing = self.get_queryset().filter(**search_criteria).first()
                        
                        # Only resolve district UUID for saving
                        slug = comp.get('district') or staff_item.get('district')
                        pk = self.resolve_district_slug_to_uuid(slug)
                        if not pk:
                            errors.append({'index': idx, 'data': staff_item,
                                           'errors': f"District slug '{slug}' could not be resolved"})
                            continue
                        
                        data = {**staff_item, 'district': pk}
                        data.pop('_composite_key', None)
                    else:
                        search_criteria = {
                            'district__slug': staff_item.get('district'),
                            'full_name': staff_item.get('full_name'),
                            'hire_date': staff_item.get('hire_date')
                        }
                        print(f"UPDATE: Looking for existing staff with direct fields: {search_criteria}")
                        existing = self.get_queryset().filter(**search_criteria).first()
                        
                        # Only resolve district UUID for saving
                        slug = staff_item.get('district')
                        pk = self.resolve_district_slug_to_uuid(slug)
                        if not pk:
                            errors.append({'index': idx, 'data': staff_item,
                                           'errors': f"District slug '{slug}' could not be resolved"})
                            continue
                        
                        data = {**staff_item, 'district': pk}

                    print(f"UPDATE: Found existing record: {existing}")

                    if not existing:
                        print(f"UPDATE: Staff not found for update")
                        errors.append({'index': idx, 'data': staff_item, 'errors': 'Staff not found for update'})
                        continue

                    serializer = self.get_serializer(existing, data=data, partial=True)
                    if serializer.is_valid():
                        saved_instance = serializer.save()
                        print(f"UPDATE: Successfully updated staff ID: {saved_instance.id}")
                        updated.append(serializer.data)
                    else:
                        print(f"UPDATE: Validation failed: {serializer.errors}")
                        errors.append({'index': idx, 'data': staff_item, 'errors': serializer.errors})
                except Exception as e:
                    print(f"UPDATE Exception at {idx}: {e}")
                    import traceback
                    print(f"UPDATE Full traceback: {traceback.format_exc()}")
                    errors.append({'index': idx, 'data': staff_item, 'errors': str(e)})

        print(f"UPDATE Final results: Updated={len(updated)}, Errors={len(errors)}")
        response_data = {'updated': len(updated), 'errors': len(errors), 'updated_data': updated}
        if errors:
            response_data['error_details'] = errors
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        staff_data = request.data.get('staff', [])
        print(f"Received {len(staff_data)} staff for bulk delete")
        if not staff_data:
            return Response({'error': 'No staff data provided'}, status=status.HTTP_400_BAD_REQUEST)

        deleted, errors = 0, []
        with transaction.atomic():
            for idx, staff_item in enumerate(staff_data):
                try:
                    print(f"Processing DELETE item {idx}: {staff_item}")
                    
                    # Normalize dates
                    comp = staff_item.get('_composite_key', {})
                    if comp and isinstance(comp.get('hire_date'), str) and 'T' in comp['hire_date']:
                        comp['hire_date'] = comp['hire_date'].split('T')[0]
                    if isinstance(staff_item.get('hire_date'), str) and 'T' in staff_item['hire_date']:
                        staff_item['hire_date'] = staff_item['hire_date'].split('T')[0]

                    # Search using district__slug (through FK relationship)
                    if comp:
                        search_criteria = {
                            'district__slug': comp.get('district'),
                            'full_name': comp.get('full_name'),
                            'hire_date': comp.get('hire_date')
                        }
                        print(f"DELETE: Looking for existing staff with composite key: {search_criteria}")
                        existing = self.get_queryset().filter(**search_criteria).first()
                    else:
                        search_criteria = {
                            'district__slug': staff_item.get('district'),
                            'full_name': staff_item.get('full_name'),
                            'hire_date': staff_item.get('hire_date')
                        }
                        print(f"DELETE: Looking for existing staff with direct fields: {search_criteria}")
                        existing = self.get_queryset().filter(**search_criteria).first()

                    print(f"DELETE: Found existing record: {existing}")

                    if existing:
                        existing.delete()
                        print(f"DELETE: Successfully deleted staff")
                        deleted += 1
                    else:
                        print(f"DELETE: Staff not found for deletion")
                        errors.append({'index': idx, 'data': staff_item, 'errors': 'Staff not found for deletion'})
                except Exception as e:
                    print(f"DELETE Exception at {idx}: {e}")
                    import traceback
                    print(f"DELETE Full traceback: {traceback.format_exc()}")
                    errors.append({'index': idx, 'data': staff_item, 'errors': str(e)})

        print(f"DELETE Final results: Deleted={deleted}, Errors={len(errors)}")
        response_data = {'deleted': deleted, 'errors': len(errors)}
        if errors:
            response_data['error_details'] = errors
        return Response(response_data, status=status.HTTP_200_OK)


class HRMetricsSummaryView(APIView):
    def get(self, request):
        data = get_hr_summary(request)
        return Response(data)


class StaffSummaryView(APIView):

    def get(self, request):
        def calculate_age(birth_date):
            today = date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        def calculate_percentage_change(current, previous):
            """Calculate percentage change between current and previous values"""
            # Convert to float to avoid Decimal/float mixing issues
            current = float(current or 0)
            previous = float(previous or 0)
            
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return round(((current - previous) / previous) * 100, 2)

        # Date filter based on Ribbon
        from_date, to_date = get_month_range_from_request(request)
        
        # Get filtering parameters
        state_filter = request.GET.get('state')  # 'all' for all states, specific state_name, or None
        district_filter = request.GET.get('district')  # 'all' for all districts, specific district_name, or None
        
        # Check if we need deltas (only for single location, not for grouped data)
        need_deltas = not (state_filter == 'all' or district_filter == 'all')
        
        # For specific state, we always need deltas for collections_per_staff
        if state_filter and state_filter != 'all' and district_filter != 'all':
            need_deltas = True
        
        # Previous month dates for delta calculations (only if needed)
        if need_deltas:
            prev_month_start = from_date - relativedelta(months=1)
            prev_month_end = (prev_month_start + relativedelta(months=1) - relativedelta(days=1))
        
        # Base queryset for staff (current month) - with optimizations
        current_staff_queryset = Staff.objects.select_related(
            'district__state',
            'department'
        ).filter(hire_date__lte=to_date)
        
        # Base queryset for staff (previous month) - only if deltas needed
        if need_deltas:
            previous_staff_queryset = Staff.objects.select_related(
                'district__state',
                'department'
            ).filter(hire_date__lte=prev_month_end)
        
        # Apply state filtering to both querysets
        if state_filter and state_filter != 'all':
            current_staff_queryset = current_staff_queryset.filter(district__state__name=state_filter)
            if need_deltas:
                previous_staff_queryset = previous_staff_queryset.filter(district__state__name=state_filter)
        
        # Apply district filtering to both querysets
        if district_filter and district_filter != 'all':
            current_staff_queryset = current_staff_queryset.filter(district__name=district_filter)
            if need_deltas:
                previous_staff_queryset = previous_staff_queryset.filter(district__name=district_filter)

        # Current month metrics - combined aggregation for better performance
        current_metrics = current_staff_queryset.aggregate(
            total_count=Count('id'),
            avg_salary=Avg('salary'),
            retained_count=Count('id', filter=Q(exit_date__isnull=True)),
            exited_count=Count('id', filter=Q(exit_date__isnull=False))
        )
        
        current_total_count = current_metrics['total_count']
        current_avg_salary = current_metrics['avg_salary'] or 0
        current_retained_count = current_metrics['retained_count']
        current_exited_count = current_metrics['exited_count']
        current_retention_rate = (current_retained_count / current_total_count * 100) if current_total_count else 0
        current_turnover_rate = (current_exited_count / current_total_count * 100) if current_total_count else 0
        
        # Current age calculation - fetch only needed fields
        current_ages = list(current_staff_queryset.filter(
            birth_date__isnull=False
        ).values_list('birth_date', flat=True))
        current_avg_age = round(sum(calculate_age(birth_date) for birth_date in current_ages) / len(current_ages)) if current_ages else 0

        # Previous month metrics - only if deltas needed
        if need_deltas:
            previous_metrics = previous_staff_queryset.aggregate(
                total_count=Count('id'),
                avg_salary=Avg('salary'),
                retained_count=Count('id', filter=Q(exit_date__isnull=True)),
                exited_count=Count('id', filter=Q(exit_date__isnull=False))
            )
            
            previous_total_count = previous_metrics['total_count']
            previous_avg_salary = previous_metrics['avg_salary'] or 0
            previous_retained_count = previous_metrics['retained_count']
            previous_exited_count = previous_metrics['exited_count']
            previous_retention_rate = (previous_retained_count / previous_total_count * 100) if previous_total_count else 0
            previous_turnover_rate = (previous_exited_count / previous_total_count * 100) if previous_total_count else 0

            # Previous age calculation
            previous_ages = list(previous_staff_queryset.filter(
                birth_date__isnull=False
            ).values_list('birth_date', flat=True))
            previous_avg_age = round(sum(calculate_age(birth_date) for birth_date in previous_ages) / len(previous_ages)) if previous_ages else 0

            # Calculate deltas
            total_staff_delta = calculate_percentage_change(current_total_count, previous_total_count)
            avg_salary_delta = calculate_percentage_change(current_avg_salary, previous_avg_salary)
            avg_age_delta = calculate_percentage_change(current_avg_age, previous_avg_age)
            retention_rate_delta = calculate_percentage_change(current_retention_rate, previous_retention_rate)
            turnover_rate_delta = calculate_percentage_change(current_turnover_rate, previous_turnover_rate)
        else:
            # No deltas for grouped data
            total_staff_delta = avg_salary_delta = avg_age_delta = retention_rate_delta = turnover_rate_delta = None

        # Distribution and gender split (using current month data) - optimized
        distribution = current_staff_queryset.values("department__name").annotate(count=Count("id"))
        gender_split = current_staff_queryset.values("gender").annotate(count=Count("id"))

        # Collections per staff calculations
        if state_filter == 'all':
            # For state=all, only get current month collections (no yearly data)
            collections_data = self.calculate_collections_per_staff_grouped_by_state(
                from_date, to_date, district_filter
            )
        elif district_filter == 'all' and state_filter and state_filter != 'all':
            # For specific state with all districts, get district-level data
            collections_data = self.calculate_collections_per_staff_grouped_by_district(
                from_date, to_date, state_filter
            )
        else:
            # For single location or specific state, get both current month and yearly data
            collections_data = self.calculate_collections_per_staff(
                from_date, to_date, 
                prev_month_start if need_deltas else None, 
                prev_month_end if need_deltas else None, 
                state_filter, district_filter, need_deltas
            )

        # Build response based on filtering type
        if state_filter == 'all':
            # Special response structure for state=all
            response_data = {
                "states": self.get_state_specific_data(current_staff_queryset, collections_data),
            }
        elif district_filter == 'all' and state_filter and state_filter != 'all':
            # All districts under a specific state
            response_data = {
                "districts": self.get_district_specific_data(current_staff_queryset, collections_data, state_filter),
            }
        elif state_filter and state_filter != 'all':
            # Specific state response - only collections data + state metrics
            response_data = {
                "collections_per_staff_current": collections_data["collections_per_staff_current"],
                "collections_per_staff_yearly": collections_data["collections_per_staff_yearly"],
                "staff_distribution": list(distribution),
                "retention_rate": round(current_retention_rate, 2),
                "turnover_rate": round(current_turnover_rate, 2),
                "gender_distribution": list(gender_split)
            }
        elif need_deltas:
            # Single location with full metrics and deltas
            response_data = {
                "total_staff": {
                    "value": current_total_count,
                    "delta": total_staff_delta
                },
                "avg_salary": {
                    "value": round(current_avg_salary),
                    "delta": avg_salary_delta
                },
                "avg_age": {
                    "value": current_avg_age,
                    "delta": avg_age_delta
                },
                "retention_rate": {
                    "value": round(current_retention_rate, 2),
                    "delta": retention_rate_delta
                },
                "turnover_rate": {
                    "value": round(current_turnover_rate, 2),
                    "delta": turnover_rate_delta
                },
                "distribution": distribution,
                "gender_split": gender_split,
                **collections_data
            }
        else:
            # Simplified response without deltas for other grouped data
            response_data = {
                "total_staff": current_total_count,
                "avg_salary": round(current_avg_salary),
                "avg_age": current_avg_age,
                "retention_rate": round(current_retention_rate, 2),
                "turnover_rate": round(current_turnover_rate, 2),
                "distribution": distribution,
                "gender_split": gender_split,
                **collections_data
            }

        return Response(response_data)

    def calculate_collections_per_staff(self, from_date, to_date, prev_month_start, prev_month_end, state_filter, district_filter, need_deltas):
        """Calculate collections per staff for selected month and yearly trend with optional delta"""
        
        # Get sales reps (they are the ones who collect) - with optimizations
        sales_reps_queryset = SalesRepresentative.objects.prefetch_related(
            'assigned_transformers__feeder__business_district__state'
        )
        
        # Apply state filtering to sales reps
        if state_filter and state_filter != 'all':
            sales_reps_queryset = sales_reps_queryset.filter(
                assigned_transformers__feeder__business_district__state__name=state_filter
            ).distinct()
        
        # Apply district filtering to sales reps
        if district_filter and district_filter != 'all':
            sales_reps_queryset = sales_reps_queryset.filter(
                assigned_transformers__feeder__business_district__name=district_filter
            ).distinct()

        # Current month collections per staff
        current_month_collections = self.get_monthly_collections_per_staff(
            from_date, to_date, sales_reps_queryset, state_filter, district_filter
        )
        
        # Previous month collections per staff for delta calculation (only if needed)
        if need_deltas and prev_month_start and prev_month_end:
            previous_month_collections = self.get_monthly_collections_per_staff(
                prev_month_start, prev_month_end, sales_reps_queryset, state_filter, district_filter
            )
            
            # Add delta for single location case only
            if isinstance(current_month_collections, dict) and 'collections_per_staff' in current_month_collections:
                current_value = float(current_month_collections['collections_per_staff'])
                previous_value = float(previous_month_collections.get('collections_per_staff', 0)) if isinstance(previous_month_collections, dict) else 0.0
                
                if previous_value == 0:
                    delta = 100.0 if current_value > 0 else 0.0
                else:
                    delta = round(((current_value - previous_value) / previous_value) * 100, 2)
                
                current_month_collections['delta'] = delta

        # Yearly collections per staff (all months in the selected year)
        yearly_collections = self.get_yearly_collections_per_staff(
            from_date, sales_reps_queryset, state_filter, district_filter
        )

        return {
            "collections_per_staff_current": current_month_collections,
            "collections_per_staff_yearly": yearly_collections
        }

    def calculate_collections_per_staff_grouped_by_state(self, from_date, to_date, district_filter):
        """Calculate collections per staff for each state (current month only)"""
        
        states = State.objects.all()
        result = {}
        
        for state in states:
            # Get sales reps for this state
            state_sales_reps = SalesRepresentative.objects.prefetch_related(
                'assigned_transformers__feeder__business_district'
            ).filter(
                assigned_transformers__feeder__business_district__state=state
            ).distinct()
            
            # Apply district filtering if specified
            if district_filter and district_filter != 'all':
                state_sales_reps = state_sales_reps.filter(
                    assigned_transformers__feeder__business_district__name=district_filter
                ).distinct()
            
            # Calculate collections for this state
            state_collections = self._calculate_monthly_collections(
                from_date, to_date, state_sales_reps, state.name, district_filter
            )
            
            result[state.name] = state_collections["per_staff"]
        
        return {"collections_per_staff_by_state": result}

    def get_state_specific_data(self, staff_queryset, collections_data):
        """Get state-specific retention, turnover, and distribution data"""
        
        states_data = {}
        states = State.objects.all()
        
        for state in states:
            # Get staff for this state
            state_staff = staff_queryset.filter(district__state=state)
            
            # Calculate metrics for this state
            state_metrics = state_staff.aggregate(
                total_count=Count('id'),
                retained_count=Count('id', filter=Q(exit_date__isnull=True)),
                exited_count=Count('id', filter=Q(exit_date__isnull=False))
            )
            
            state_total = state_metrics['total_count']
            state_retained = state_metrics['retained_count']
            state_exited = state_metrics['exited_count']
            
            state_retention_rate = (state_retained / state_total * 100) if state_total else 0
            state_turnover_rate = (state_exited / state_total * 100) if state_total else 0
            
            # Get department distribution for this state
            state_distribution = state_staff.values("department__name").annotate(
                count=Count("id")
            )
            
            # Get gender distribution for this state
            state_gender_split = state_staff.values("gender").annotate(
                count=Count("id")
            )
            
            # Get collections per staff for this state
            collections_per_staff = collections_data.get("collections_per_staff_by_state", {}).get(state.name, 0)
            
            states_data[state.name] = {
                "collections_per_staff": collections_per_staff,
                "retention_rate": round(state_retention_rate, 2),
                "turnover_rate": round(state_turnover_rate, 2),
                "department_distribution": list(state_distribution),
                "gender_distribution": list(state_gender_split)
            }
        
    def calculate_collections_per_staff_grouped_by_district(self, from_date, to_date, state_filter):
        """Calculate collections per staff for each district under a specific state (current month only)"""
        
        # Get districts under the specified state  
        from hr.models import BusinessDistrict
        districts = BusinessDistrict.objects.filter(state__name=state_filter)
        result = {}
        
        for district in districts:
            # Get sales reps for this district
            district_sales_reps = SalesRepresentative.objects.prefetch_related(
                'assigned_transformers__feeder__business_district'
            ).filter(
                assigned_transformers__feeder__business_district=district
            ).distinct()
            
            # Calculate collections for this district
            district_collections = self._calculate_monthly_collections(
                from_date, to_date, district_sales_reps, state_filter, district.name
            )
            
            result[district.name] = district_collections["per_staff"]
        
        return {"collections_per_staff_by_district": result}

    def get_district_specific_data(self, staff_queryset, collections_data, state_filter):
        """Get district-specific data for all districts under a state"""
        
        from hr.models import BusinessDistrict
        districts_data = {}
        districts = BusinessDistrict.objects.filter(state__name=state_filter)
        
        for district in districts:
            # Get staff for this district
            district_staff = staff_queryset.filter(district=district)
            
            # Calculate metrics for this district
            district_metrics = district_staff.aggregate(
                total_count=Count('id'),
                retained_count=Count('id', filter=Q(exit_date__isnull=True)),
                exited_count=Count('id', filter=Q(exit_date__isnull=False))
            )
            
            district_total = district_metrics['total_count']
            district_retained = district_metrics['retained_count']
            district_exited = district_metrics['exited_count']
            
            district_retention_rate = (district_retained / district_total * 100) if district_total else 0
            district_turnover_rate = (district_exited / district_total * 100) if district_total else 0
            
            # Get gender distribution for this district
            district_gender_split = district_staff.values("gender").annotate(
                count=Count("id")
            )
            
            # Get collections per staff for this district
            collections_per_staff = collections_data.get("collections_per_staff_by_district", {}).get(district.name, 0)
            
            districts_data[district.name] = {
                "collections_per_staff": collections_per_staff,
                "staff_count": district_total,
                "retention_rate": round(district_retention_rate, 2),
                "turnover_rate": round(district_turnover_rate, 2),
                "gender_distribution": list(district_gender_split)
            }
        
        return districts_data

    def get_monthly_collections_per_staff(self, from_date, to_date, sales_reps_queryset, state_filter, district_filter):
        """Get collections per staff for the selected month"""
        
        if state_filter == 'all':
            # Return data grouped by state
            states = State.objects.all()
            result = {}
            
            for state in states:
                state_sales_reps = sales_reps_queryset.filter(
                    assigned_transformers__feeder__business_district__state=state
                ).distinct()
                
                state_collections = self._calculate_monthly_collections(
                    from_date, to_date, state_sales_reps, state.name, district_filter
                )
                
                result[state.name] = {
                    "total_collections": state_collections["total"],
                    "total_sales_reps": state_collections["count"],
                    "collections_per_staff": state_collections["per_staff"]
                }
            
            return result
            
        elif district_filter == 'all':
            # Return data grouped by business district
            districts_queryset = BusinessDistrict.objects.all()
            if state_filter:
                districts_queryset = districts_queryset.filter(state__name=state_filter)
                
            result = {}
            
            for district in districts_queryset:
                district_sales_reps = sales_reps_queryset.filter(
                    assigned_transformers__feeder__business_district=district
                ).distinct()
                
                district_collections = self._calculate_monthly_collections(
                    from_date, to_date, district_sales_reps, state_filter, district.name
                )
                
                result[district.name] = {
                    "total_collections": district_collections["total"],
                    "total_sales_reps": district_collections["count"],
                    "collections_per_staff": district_collections["per_staff"]
                }
            
            return result
        
        else:
            # Single aggregated result
            collections_data = self._calculate_monthly_collections(
                from_date, to_date, sales_reps_queryset, state_filter, district_filter
            )
            
            return {
                "total_collections": collections_data["total"],
                "total_sales_reps": collections_data["count"],
                "collections_per_staff": collections_data["per_staff"]
            }

    def get_yearly_collections_per_staff(self, from_date, sales_reps_queryset, state_filter, district_filter):
        """Get collections per staff for all months in the selected year"""
        
        year = from_date.year
        monthly_data = []
        
        for month in range(1, 13):
            month_start = datetime(year, month, 1).date()
            month_end = (datetime(year, month, 1) + relativedelta(months=1) - relativedelta(days=1)).date()
            
            if state_filter == 'all':
                # Group by state for each month
                states = State.objects.all()
                month_state_data = {}
                
                for state in states:
                    state_sales_reps = sales_reps_queryset.filter(
                        assigned_transformers__feeder__business_district__state=state
                    ).distinct()
                    
                    state_collections = self._calculate_monthly_collections(
                        month_start, month_end, state_sales_reps, state.name, district_filter
                    )
                    
                    month_state_data[state.name] = state_collections["per_staff"]
                
                monthly_data.append({
                    "month": month_start.strftime("%b"),
                    "year": year,
                    "states": month_state_data
                })
                
            elif district_filter == 'all':
                # Group by district for each month
                districts_queryset = BusinessDistrict.objects.all()
                if state_filter:
                    districts_queryset = districts_queryset.filter(state__name=state_filter)
                    
                month_district_data = {}
                
                for district in districts_queryset:
                    district_sales_reps = sales_reps_queryset.filter(
                        assigned_transformers__feeder__business_district=district
                    ).distinct()
                    
                    district_collections = self._calculate_monthly_collections(
                        month_start, month_end, district_sales_reps, state_filter, district.id
                    )
                    
                    month_district_data[district.name] = district_collections["per_staff"]
                
                monthly_data.append({
                    "month": month_start.strftime("%b"),
                    "year": year,
                    "districts": month_district_data
                })
            
            else:
                # Single aggregated result for each month
                collections_data = self._calculate_monthly_collections(
                    month_start, month_end, sales_reps_queryset, state_filter, district_filter
                )
                
                monthly_data.append({
                    "month": month_start.strftime("%b"),
                    "year": year,
                    "collections_per_staff": collections_data["per_staff"]
                })
        
        return monthly_data

    def _calculate_monthly_collections(self, from_date, to_date, sales_reps_queryset, state_filter, district_filter):
        """Helper method to calculate collections for a given period and sales reps"""
        
        # Get collections from DailyCollection
        collections_queryset = DailyCollection.objects.filter(
            date__range=(from_date, to_date),
            sales_rep__in=sales_reps_queryset
        )
        
        # Apply additional filtering if needed
        # Note: DailyCollection filtering removed since distribution_transformer field may not exist yet
        # if state_filter and state_filter != 'all':
        #     collections_queryset = collections_queryset.filter(
        #         distribution_transformer__feeder__business_district__state__name=state_filter
        #     )
        # 
        # if district_filter and district_filter != 'all':
        #     collections_queryset = collections_queryset.filter(
        #         distribution_transformer__feeder__business_district__name=district_filter
        #     )
        
        total_collections = collections_queryset.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Also check MonthlyCommercialSummary for additional collections data
        monthly_summary_queryset = MonthlyCommercialSummary.objects.filter(
            month__range=(from_date, to_date),
            sales_rep__in=sales_reps_queryset
        )
        
        if state_filter and state_filter != 'all':
            monthly_summary_queryset = monthly_summary_queryset.filter(
                sales_rep__assigned_transformers__feeder__business_district__state__name=state_filter
            ).distinct()
        
        if district_filter and district_filter != 'all':
            monthly_summary_queryset = monthly_summary_queryset.filter(
                sales_rep__assigned_transformers__feeder__business_district__name=district_filter
            ).distinct()
        
        summary_collections = monthly_summary_queryset.aggregate(
            total=Sum('revenue_collected')
        )['total'] or 0
        
        # Use the higher of the two collection amounts (to avoid double counting)
        # Convert to float to avoid Decimal/float mixing
        total_collections = float(max(total_collections, summary_collections))
        
        sales_reps_count = sales_reps_queryset.count()
        collections_per_staff = round(total_collections / sales_reps_count, 2) if sales_reps_count > 0 else 0.0
        
        return {
            "total": total_collections,
            "count": sales_reps_count,
            "per_staff": collections_per_staff
        }
