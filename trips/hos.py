from datetime import date, timedelta


def simulate_trip(
    distance_to_pickup,
    duration_to_pickup,
    distance_pickup_to_dropoff,
    duration_pickup_to_dropoff,
    cycle_used_hours,
    current_location_label="",
    pickup_location_label="",
    dropoff_location_label="",
    start_date=None,
):
    """
    Simulates a full trip respecting HOS rules.
    Returns a list of day objects, each containing a schedule of segments.

    HOS Rules applied:
    - Max 11 hrs driving per shift
    - Max 14 hr on-duty window from first activity
    - 10 hr off-duty rest required after shift
    - 30 min break after 8 cumulative driving hours
    - Fueling stop (30 min) every 1000 miles
    - 1 hr pickup (On Duty Not Driving) at start
    - 1 hr dropoff (On Duty Not Driving) at end
    - 70 hr / 8 day cycle limit
    """

    # ── Constants ──────────────────────────────────────────────
    MAX_DRIVE_PER_SHIFT  = 11.0   # hours
    MAX_WINDOW           = 14.0   # hours (on-duty window per shift)
    REQUIRED_REST        = 10.0   # hours off-duty after shift
    BREAK_AFTER_DRIVE    = 8.0    # cumulative drive hours before mandatory break
    BREAK_DURATION       = 0.5    # hours (30 min)
    FUEL_EVERY_MILES     = 1000.0
    FUEL_STOP_DURATION   = 0.5    # hours (30 min)
    PICKUP_DURATION      = 1.0    # hours
    DROPOFF_DURATION     = 1.0    # hours
    AVG_SPEED            = 55.0   # mph
    SHIFT_START_HOUR     = 6.0    # 06:00 AM

    # ── State ──────────────────────────────────────────────────
    if start_date is None:
        start_date = date.today()

    remaining_cycle       = 70.0 - cycle_used_hours
    drive_hours_remaining = duration_to_pickup + duration_pickup_to_dropoff
    total_distance        = distance_to_pickup + distance_pickup_to_dropoff

    miles_driven      = 0.0
    miles_since_fuel  = 0.0
    pickup_done       = False
    dropoff_done      = False

    # Track which leg we are on to compute per-day miles correctly
    # Leg 1: current → pickup, Leg 2: pickup → dropoff
    leg1_hours_remaining = duration_to_pickup
    leg2_hours_remaining = duration_pickup_to_dropoff

    days   = []
    day_no = 1

    while (drive_hours_remaining > 0 or not dropoff_done):

        # Safety cap
        if day_no > 14:
            break

        current_time      = SHIFT_START_HOUR
        shift_drive       = 0.0
        window_used       = 0.0
        drive_since_break = 0.0
        day_miles         = 0.0
        segments          = []
        remarks           = []

        # ── Determine From / To labels for this day ────────────
        if day_no == 1:
            from_label = current_location_label
        else:
            from_label = f"Rest stop (Day {day_no - 1})"

        # ── Helper to add a segment ────────────────────────────
        def add_segment(status, hours, label=""):
            nonlocal current_time, window_used
            seg = {
                "status": status,
                "start":  _fmt(current_time),
                "end":    _fmt(current_time + hours),
                "hours":  round(hours, 2),
                "label":  label,
            }
            segments.append(seg)
            current_time += hours
            if status in ("driving", "on_duty"):
                window_used += hours

        # ── Pickup on Day 1 ────────────────────────────────────
        if day_no == 1 and not pickup_done:
            add_segment("on_duty", PICKUP_DURATION, f"Pickup at {pickup_location_label}")
            remarks.append(f"Pickup at {pickup_location_label}")
            pickup_done = True

        # ── Drive as much as allowed this shift ────────────────
        while (
            drive_hours_remaining > 0
            and shift_drive < MAX_DRIVE_PER_SHIFT
            and window_used < MAX_WINDOW
            and remaining_cycle > 0
        ):
            can_drive = min(
                drive_hours_remaining,
                MAX_DRIVE_PER_SHIFT  - shift_drive,
                MAX_WINDOW           - window_used,
                remaining_cycle,
                BREAK_AFTER_DRIVE    - drive_since_break,
            )

            # Check if a fuel stop lands within this segment
            miles_this_seg = can_drive * AVG_SPEED
            if miles_since_fuel + miles_this_seg >= FUEL_EVERY_MILES:
                miles_to_fuel = FUEL_EVERY_MILES - miles_since_fuel
                hours_to_fuel = miles_to_fuel / AVG_SPEED

                if hours_to_fuel > 0:
                    add_segment("driving", hours_to_fuel)
                    _deduct(hours_to_fuel, locals())
                    shift_drive           += hours_to_fuel
                    drive_since_break     += hours_to_fuel
                    drive_hours_remaining -= hours_to_fuel
                    day_miles             += miles_to_fuel
                    miles_driven          += miles_to_fuel
                    remaining_cycle       -= hours_to_fuel
                    leg1_hours_remaining  -= min(hours_to_fuel, leg1_hours_remaining)
                    if leg1_hours_remaining <= 0:
                        leg2_hours_remaining -= max(0, hours_to_fuel - duration_to_pickup)

                # Fuel stop
                fuel_loc = f"Mile {round(miles_driven)}"
                add_segment("on_duty", FUEL_STOP_DURATION, f"Fuel stop ({fuel_loc})")
                remarks.append(f"Fuel stop at {fuel_loc}")
                miles_since_fuel = 0.0
                continue

            # Normal drive segment
            add_segment("driving", can_drive)
            shift_drive           += can_drive
            drive_since_break     += can_drive
            drive_hours_remaining -= can_drive
            day_miles             += can_drive * AVG_SPEED
            miles_driven          += can_drive * AVG_SPEED
            miles_since_fuel      += can_drive * AVG_SPEED
            remaining_cycle       -= can_drive

            # Mandatory 30-min break after 8 hrs driving
            if drive_since_break >= BREAK_AFTER_DRIVE and drive_hours_remaining > 0:
                add_segment("off_duty", BREAK_DURATION, "30-min mandatory break")
                drive_since_break = 0.0

        # ── Dropoff on last active day ─────────────────────────
        if drive_hours_remaining <= 0 and not dropoff_done:
            add_segment("on_duty", DROPOFF_DURATION, f"Dropoff at {dropoff_location_label}")
            remarks.append(f"Dropoff at {dropoff_location_label}")
            dropoff_done = True

        # ── To label ──────────────────────────────────────────
        if dropoff_done:
            to_label = dropoff_location_label
        else:
            to_label = f"Rest stop (Day {day_no})"

        # ── End of shift rest ─────────────────────────────────
        rest_start = current_time
        remaining_day = 24.0 - rest_start

        if remaining_day > 0:
            if remaining_day >= REQUIRED_REST:
                add_segment("off_duty", REQUIRED_REST, "Off-duty rest")
                if current_time < 24.0:
                    add_segment("off_duty", 24.0 - current_time, "")
            else:
                # Rest spills to next day — just fill today
                add_segment("off_duty", remaining_day, "Off-duty rest (cont. next day)")

        # ── Compute total hours per status row ─────────────────
        def total_hours_for(status_list):
            return round(
                sum(s["hours"] for s in segments if s["status"] in status_list), 2
            )

        # ── Build day object ───────────────────────────────────
        current_day_date = start_date + timedelta(days=day_no - 1)

        days.append({
            "day":               day_no,
            "date":              current_day_date.strftime("%m/%d/%Y"),
            "from":              from_label,
            "to":                to_label,
            "miles_driven_today": round(day_miles, 1),
            "total_miles":       round(miles_driven, 1),
            "segments":          segments,
            "remarks":           remarks,
            "totals": {
                "off_duty":      total_hours_for(["off_duty"]),
                "sleeper_berth": 0.0,   # not used in this simulation
                "driving":       total_hours_for(["driving"]),
                "on_duty":       total_hours_for(["on_duty"]),
            },
        })

        day_no += 1

        if dropoff_done:
            break

    return days


# ── Helpers ────────────────────────────────────────────────────

def _deduct(hours, state):
    """No-op placeholder kept for readability in the loop above."""
    pass


def _fmt(hours):
    """Convert float hours to HH:MM string. e.g. 13.5 → '13:30'"""
    hours = max(0.0, min(hours, 24.0))
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"