from datetime import date

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import TripRequestSerializer
from .routing import ensure_coords, get_route
from .hos import simulate_trip


@api_view(["POST"])
def plan_trip(request):
    serializer = TripRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        # ── Step 1: Resolve coordinates ───────────────────────
        current_coords  = ensure_coords(data["current_location"])
        pickup_coords   = ensure_coords(data["pickup_location"])
        dropoff_coords  = ensure_coords(data["dropoff_location"])

        # ── Step 2: Get route distances and durations ─────────
        dist_to_pickup,       dur_to_pickup       = get_route(current_coords, pickup_coords)
        dist_pickup_dropoff,  dur_pickup_dropoff  = get_route(pickup_coords,  dropoff_coords)

        # ── Step 3: Run HOS simulation ────────────────────────
        days = simulate_trip(
            distance_to_pickup             = dist_to_pickup,
            duration_to_pickup             = dur_to_pickup,
            distance_pickup_to_dropoff     = dist_pickup_dropoff,
            duration_pickup_to_dropoff     = dur_pickup_dropoff,
            cycle_used_hours               = data["cycle_used_hours"],
            current_location_label         = data["current_location"]["label"],
            pickup_location_label          = data["pickup_location"]["label"],
            dropoff_location_label         = data["dropoff_location"]["label"],
            start_date                     = date.today(),
        )

        # ── Step 4: Return response ───────────────────────────
        return Response({
            "total_distance_miles": round(dist_to_pickup + dist_pickup_dropoff, 2),
            "total_duration_hours": round(dur_to_pickup  + dur_pickup_dropoff,  2),
            "total_days":           len(days),
            "coordinates": {
                "current":  {"lat": current_coords[0],  "lng": current_coords[1]},
                "pickup":   {"lat": pickup_coords[0],   "lng": pickup_coords[1]},
                "dropoff":  {"lat": dropoff_coords[0],  "lng": dropoff_coords[1]},
            },
            "days": days,
        })

    except ValueError as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {"error": "Something went wrong.", "detail": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )