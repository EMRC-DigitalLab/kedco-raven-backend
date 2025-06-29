from django.contrib import admin
from .models import State, BusinessDistrict, InjectionSubstation, Feeder, DistributionTransformer, Band

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name', 'slug']


@admin.register(BusinessDistrict)
class BusinessDistrictAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'state']
    search_fields = ['name', 'slug']
    list_filter = ['state']


@admin.register(InjectionSubstation)
class InjectionSubstationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug',]
    search_fields = ['name', 'slug']


@admin.register(Feeder)
class FeederAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'substation']
    search_fields = ['name', 'slug']


@admin.register(DistributionTransformer)
class DistributionTransformerAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'feeder']
    search_fields = ['name', 'slug']


@admin.register(Band)
class BandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name', 'slug']
