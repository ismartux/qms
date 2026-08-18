from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
import json

from org.models import (
    Company,
    Plant,
    Department,
    Shop,
    Line,
    Station,
    Product,
)


# =====================================================
# Helper Functions
# =====================================================

def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


def get_common_context():
    """Get common context data for templates"""
    return {
        'models': {
            'company': {'name': 'Company', 'icon': '🏢'},
            'plant': {'name': 'Plant', 'icon': '🏭'},
            'department': {'name': 'Department', 'icon': '📋'},
            'shop': {'name': 'Shop', 'icon': '🔧'},
            'line': {'name': 'Line', 'icon': '⚙️'},
            'station': {'name': 'Station', 'icon': '📍'},
            'product': {'name': 'Product', 'icon': '📦'},
        }
    }


# =====================================================
# Dashboard / Home
# =====================================================

@login_required
def org_dashboard(request):
    """Organization Setup Dashboard"""
    context = get_common_context()
    
    # Get counts for each model
    context['stats'] = {
        'companies': Company.objects.count(),
        'plants': Plant.objects.count(),
        'departments': Department.objects.count(),
        'shops': Shop.objects.count(),
        'lines': Line.objects.count(),
        'stations': Station.objects.count(),
        'products': Product.objects.count(),
    }
    
    context['is_superuser'] = request.user.is_superuser
    
    return render(request, 'org/dashboard.html', context)


# =====================================================
# Generic CRUD Views
# =====================================================

class GenericCRUDView:
    """Generic CRUD operations for organization models"""
    
    def __init__(self, model, model_name, fields, template_prefix, 
                 list_template=None, form_template=None,
                 parent_field=None, parent_model=None):
        self.model = model
        self.model_name = model_name
        self.fields = fields
        self.template_prefix = template_prefix
        self.list_template = list_template or f'org/{template_prefix}_list.html'
        self.form_template = form_template or f'org/{template_prefix}_form.html'
        self.parent_field = parent_field
        self.parent_model = parent_model
    
    def list_view(self, request):
        """List all records with search and pagination"""
        search_query = request.GET.get('search', '')
        page_number = request.GET.get('page', 1)
        
        # Base queryset
        queryset = self.model.objects.all()
        
        # Apply search filter
        if search_query:
            search_filter = Q()
            for field in self.fields:
                if field in ['code', 'name']:
                    search_filter |= Q(**{f'{field}__icontains': search_query})
            queryset = queryset.filter(search_filter)
        
        # Order by name or code
        if hasattr(self.model, 'name'):
            queryset = queryset.order_by('name')
        else:
            queryset = queryset.order_by('code')
        
        # Pagination
        paginator = Paginator(queryset, 20)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'model_name': self.model_name,
            'model_name_plural': self.model_name + 's',
            'fields': self.fields,
            'is_superuser': request.user.is_superuser,
            'can_add': True,
            'can_edit': True,
            'can_delete': request.user.is_superuser,
        }
        
        return render(request, self.list_template, context)
    
    def create_view(self, request):
        """Create new record"""
        if request.method == 'POST':
            try:
                data = {}
                for field in self.fields:
                    if field == 'company':
                        data['company'] = get_object_or_404(Company, id=request.POST.get('company'))
                    elif field == 'plant':
                        data['plant'] = get_object_or_404(Plant, id=request.POST.get('plant'))
                    elif field == 'shop':
                        data['shop'] = get_object_or_404(Shop, id=request.POST.get('shop'))
                    elif field == 'line':
                        data['line'] = get_object_or_404(Line, id=request.POST.get('line'))
                    elif field in request.POST:
                        data[field] = request.POST.get(field)
                
                record = self.model(**data)
                record.full_clean()  # Validate
                record.save()
                
                messages.success(request, f'{self.model_name} created successfully!')
                return redirect(f'org:{self.model_name}_list')
            
            except Exception as e:
                messages.error(request, f'Error creating {self.model_name}: {str(e)}')
        
        # GET request - show form
        context = {
            'model_name': self.model_name,
            'action': 'Create',
            'companies': Company.objects.filter(is_active=True) if self.model_name in ['Plant', 'Product', 'Department', 'Shop'] else None,
            'plants': Plant.objects.filter(is_active=True) if self.model_name in ['Department', 'Shop', 'Line', 'Station', 'Product'] else None,
            'shops': Shop.objects.filter(is_active=True) if self.model_name in ['Line', 'Station'] else None,
            'lines': Line.objects.filter(is_active=True) if self.model_name == 'Station' else None,
        }
        
        return render(request, self.form_template, context)
    
    def edit_view(self, request, pk):
        """Edit existing record"""
        record = get_object_or_404(self.model, pk=pk)
        
        if request.method == 'POST':
            try:
                for field in self.fields:
                    if field == 'company':
                        record.company = get_object_or_404(Company, id=request.POST.get('company'))
                    elif field == 'plant':
                        record.plant = get_object_or_404(Plant, id=request.POST.get('plant'))
                    elif field == 'shop':
                        record.shop = get_object_or_404(Shop, id=request.POST.get('shop'))
                    elif field == 'line':
                        record.line = get_object_or_404(Line, id=request.POST.get('line'))
                    elif field in request.POST:
                        setattr(record, field, request.POST.get(field))
                
                record.full_clean()  # Validate
                record.save()
                
                messages.success(request, f'{self.model_name} updated successfully!')
                return redirect(f'org:{self.model_name}_list')
            
            except Exception as e:
                messages.error(request, f'Error updating {self.model_name}: {str(e)}')
        
        context = {
            'record': record,
            'model_name': self.model_name,
            'action': 'Edit',
            'companies': Company.objects.filter(is_active=True) if self.model_name in ['Plant', 'Product', 'Department', 'Shop'] else None,
            'plants': Plant.objects.filter(is_active=True) if self.model_name in ['Department', 'Shop', 'Line', 'Station', 'Product'] else None,
            'shops': Shop.objects.filter(is_active=True) if self.model_name in ['Line', 'Station'] else None,
            'lines': Line.objects.filter(is_active=True) if self.model_name == 'Station' else None,
        }
        
        return render(request, self.form_template, context)
    
    @user_passes_test(is_superuser)
    def delete_view(self, request, pk):
        """Delete record - SUPERUSER ONLY"""
        if request.method == 'POST':
            try:
                record = get_object_or_404(self.model, pk=pk)
                record_name = str(record)
                record.delete()
                
                messages.success(request, f'{self.model_name} "{record_name}" deleted successfully!')
            except Exception as e:
                messages.error(request, f'Error deleting {self.model_name}: {str(e)}')
        
        return redirect(f'org:{self.model_name}_list')


# =====================================================
# Initialize CRUD Views for each model
# =====================================================

company_crud = GenericCRUDView(
    model=Company,
    model_name='company',
    fields=['code', 'name'],
    template_prefix='company'
)

plant_crud = GenericCRUDView(
    model=Plant,
    model_name='plant',
    fields=['company', 'code', 'name', 'timezone'],
    template_prefix='plant'
)

department_crud = GenericCRUDView(
    model=Department,
    model_name='department',
    fields=['plant', 'code', 'name', 'description'],
    template_prefix='department'
)

shop_crud = GenericCRUDView(
    model=Shop,
    model_name='shop',
    fields=['plant', 'code', 'name'],
    template_prefix='shop'
)

line_crud = GenericCRUDView(
    model=Line,
    model_name='line',
    fields=['shop', 'code', 'name'],
    template_prefix='line'
)

station_crud = GenericCRUDView(
    model=Station,
    model_name='station',
    fields=['line', 'code', 'name'],
    template_prefix='station'
)

product_crud = GenericCRUDView(
    model=Product,
    model_name='product',
    fields=['company', 'plant', 'code', 'name', 'category', 'position', 'brand'],
    template_prefix='product'
)


# =====================================================
# URL-named View Functions
# =====================================================

@login_required
def company_list(request):
    return company_crud.list_view(request)

@login_required
def company_create(request):
    return company_crud.create_view(request)

@login_required
def company_edit(request, pk):
    return company_crud.edit_view(request, pk)

@login_required
def company_delete(request, pk):
    return company_crud.delete_view(request, pk)


@login_required
def plant_list(request):
    return plant_crud.list_view(request)

@login_required
def plant_create(request):
    return plant_crud.create_view(request)

@login_required
def plant_edit(request, pk):
    return plant_crud.edit_view(request, pk)

@login_required
def plant_delete(request, pk):
    return plant_crud.delete_view(request, pk)


@login_required
def department_list(request):
    return department_crud.list_view(request)

@login_required
def department_create(request):
    return department_crud.create_view(request)

@login_required
def department_edit(request, pk):
    return department_crud.edit_view(request, pk)

@login_required
def department_delete(request, pk):
    return department_crud.delete_view(request, pk)


@login_required
def shop_list(request):
    return shop_crud.list_view(request)

@login_required
def shop_create(request):
    return shop_crud.create_view(request)

@login_required
def shop_edit(request, pk):
    return shop_crud.edit_view(request, pk)

@login_required
def shop_delete(request, pk):
    return shop_crud.delete_view(request, pk)


@login_required
def line_list(request):
    return line_crud.list_view(request)

@login_required
def line_create(request):
    return line_crud.create_view(request)

@login_required
def line_edit(request, pk):
    return line_crud.edit_view(request, pk)

@login_required
def line_delete(request, pk):
    return line_crud.delete_view(request, pk)


@login_required
def station_list(request):
    return station_crud.list_view(request)

@login_required
def station_create(request):
    return station_crud.create_view(request)

@login_required
def station_edit(request, pk):
    return station_crud.edit_view(request, pk)

@login_required
def station_delete(request, pk):
    return station_crud.delete_view(request, pk)


@login_required
def product_list(request):
    return product_crud.list_view(request)

@login_required
def product_create(request):
    return product_crud.create_view(request)

@login_required
def product_edit(request, pk):
    return product_crud.edit_view(request, pk)

@login_required
def product_delete(request, pk):
    return product_crud.delete_view(request, pk)


# =====================================================
# AJAX Views for Dynamic Dropdowns
# =====================================================

@login_required
def ajax_get_plants(request):
    """Get plants for a company (AJAX)"""
    company_id = request.GET.get('company_id')
    plants = Plant.objects.filter(company_id=company_id, is_active=True).values('id', 'name', 'code')
    return JsonResponse(list(plants), safe=False)


@login_required
def ajax_get_departments(request):
    """Get departments for a plant (AJAX)"""
    plant_id = request.GET.get('plant_id')
    departments = Department.objects.filter(plant_id=plant_id, is_active=True).values('id', 'name', 'code')
    return JsonResponse(list(departments), safe=False)


@login_required
def ajax_get_shops(request):
    """Get shops for a plant (AJAX)"""
    plant_id = request.GET.get('plant_id')
    shops = Shop.objects.filter(plant_id=plant_id, is_active=True).values('id', 'name', 'code')
    return JsonResponse(list(shops), safe=False)


@login_required
def ajax_get_lines(request):
    """Get lines for a shop (AJAX)"""
    shop_id = request.GET.get('shop_id')
    lines = Line.objects.filter(shop_id=shop_id, is_active=True).values('id', 'name', 'code')
    return JsonResponse(list(lines), safe=False)


@login_required
def ajax_get_stations(request):
    """Get stations for a line (AJAX)"""
    line_id = request.GET.get('line_id')
    stations = Station.objects.filter(line_id=line_id, is_active=True).values('id', 'name', 'code')
    return JsonResponse(list(stations), safe=False)