from rest_framework import serializers
from .models import *

class EnergyDeliveredSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnergyDelivered
        fields = '__all__'


class HourlyLoadSerializer(serializers.ModelSerializer):
    feeder = serializers.SlugRelatedField(
        queryset=Feeder.objects.all(),
        slug_field='slug'
    )
    
    class Meta:
        model = HourlyLoad
        fields = '__all__'


class FeederInterruptionSerializer(serializers.ModelSerializer):
    duration_hours = serializers.FloatField(read_only=True)

    feeder = serializers.SlugRelatedField(
        queryset=Feeder.objects.all(),
        slug_field='slug'
    )

    class Meta:
        model = FeederInterruption
        fields = '__all__'


class DailyHoursOfSupplySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyHoursOfSupply
        fields = '__all__'


class FeederAvailabilitySerializer(serializers.Serializer):
    feeder_name = serializers.CharField()
    voltage_level = serializers.CharField()
    avg_hours_of_supply = serializers.FloatField()
    duration_of_interruptions = serializers.FloatField()
    turnaround_time = serializers.FloatField()
    ftc = serializers.IntegerField()
