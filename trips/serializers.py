from rest_framework import serializers


class LocationSerializer(serializers.Serializer):
    label = serializers.CharField()
    lat   = serializers.FloatField(required=False, allow_null=True)
    lng   = serializers.FloatField(required=False, allow_null=True)


class TripRequestSerializer(serializers.Serializer):
    current_location  = LocationSerializer()
    pickup_location   = LocationSerializer()
    dropoff_location  = LocationSerializer()
    cycle_used_hours  = serializers.FloatField(min_value=0, max_value=70)