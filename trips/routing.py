import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
OSRM_URL      = "https://router.project-osrm.org/route/v1/driving"
HEADERS       = {"User-Agent": "TripLogApp/1.0"}


def geocode(label):
    """Convert a place name to (lat, lng). Returns (lat, lng) or raises."""
    res = requests.get(
        f"{NOMINATIM_URL}/search",
        params={"q": label, "format": "json", "limit": 1},
        headers=HEADERS,
        timeout=10,
    )
    results = res.json()
    if not results:
        raise ValueError(f"Could not geocode: {label}")
    return float(results[0]["lat"]), float(results[0]["lon"])


def ensure_coords(location):
    """
    If lat/lng already provided by frontend use them.
    Otherwise geocode from the label.
    Returns (lat, lng).
    """
    if location.get("lat") and location.get("lng"):
        return location["lat"], location["lng"]
    return geocode(location["label"])


def get_route(origin, destination):
    """
    Call OSRM to get distance (miles) and duration (hours) between two (lat,lng) tuples.
    OSRM is completely free, no API key needed.
    """
    coord_str = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    res = requests.get(
        f"{OSRM_URL}/{coord_str}",
        params={"overview": "false"},
        timeout=15,
    )
    data = res.json()

    if data.get("code") != "Ok":
        raise ValueError("Could not get route from OSRM.")

    route    = data["routes"][0]
    distance = route["distance"] / 1609.34   # meters → miles
    duration = route["duration"] / 3600      # seconds → hours

    return round(distance, 2), round(duration, 2)