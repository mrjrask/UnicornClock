import machine
import math
import ntptime
import time


def debounce(ms=250):
    """Button debounce

    The args `ms` is the delay in milliseconds below which
    the function call is ignored.
    """
    timeout = time.ticks_ms()

    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal timeout

            if time.ticks_diff(time.ticks_ms(), timeout) < ms:
                return

            func(*args, **kwargs)

            timeout = time.ticks_ms()
        return wrapper

    return decorator


@micropython.native  # noqa: F821
def from_hsv(h, s, v):
    i = math.floor(h * 6.0)
    f = h * 6.0 - i
    v *= 255.0
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)

    i = int(i) % 6
    if i == 0:
        return int(v), int(t), int(p)
    if i == 1:
        return int(q), int(v), int(p)
    if i == 2:
        return int(p), int(v), int(t)
    if i == 3:
        return int(p), int(q), int(v)
    if i == 4:
        return int(t), int(p), int(v)
    if i == 5:
        return int(v), int(p), int(q)


def _nth_weekday(year, month, weekday, occurrence=1):
    """Return the day of month for the nth ``weekday``.

    ``weekday`` uses the Python convention where Monday is 0 and Sunday is 6.
    """
    first_weekday = time.localtime(time.mktime((year, month, 1, 0, 0, 0, 0, 0)))[6]
    days_until_weekday = (weekday - first_weekday) % 7
    return 1 + days_until_weekday + (occurrence - 1) * 7


def _is_us_dst(local_time):
    """Check if a local time is in the US daylight saving period.

    Daylight saving time starts on the second Sunday in March at 02:00 local
    time and ends on the first Sunday in November at 02:00 local time.
    """
    year, month, day, hour = local_time[0], local_time[1], local_time[2], local_time[3]

    if month < 3 or month > 11:
        return False

    if 3 < month < 11:
        return True

    second_sunday_march = _nth_weekday(year, 3, 6, 2)
    first_sunday_november = _nth_weekday(year, 11, 6, 1)

    if month == 3:
        if day > second_sunday_march:
            return True
        if day == second_sunday_march and hour >= 2:
            return True
        return False

    if month == 11:
        if day < first_sunday_november:
            return True
        if day == first_sunday_november and hour < 2:
            return True
        return False

    return False


def _get_us_central_offset(rtc_time):
    """Return the current UTC offset for the US Central timezone."""
    y, mo, d, wd, h, m, s, _ = rtc_time

    # Start with standard time offset (-6 hours) and adjust for DST.
    utc_seconds = time.mktime((y, mo, d, h, m, s, wd, 0))
    standard_offset = -6
    local_time = time.localtime(utc_seconds + standard_offset * 3600)

    if _is_us_dst(local_time):
        return -5

    return standard_offset


def get_timezone_offset(timezone, rtc_time):
    """Return a UTC offset for a timezone name.

    The function currently supports ``"US/Central"`` and ``"America/Chicago"``.
    """
    if timezone in ("US/Central", "America/Chicago"):
        return _get_us_central_offset(rtc_time)

    raise ValueError("Unsupported timezone: %s" % timezone)


def set_time(utc_offset=None, timezone="US/Central"):
    # There is no timezone support in Micropython,
    # we need to use tricks

    ntptime.settime()

    rtc = machine.RTC()

    y, mo, d, wd, h, m, s, ss = rtc.datetime()

    if timezone:
        utc_offset = get_timezone_offset(timezone, (y, mo, d, wd, h, m, s, ss))
    elif utc_offset is None:
        utc_offset = 0

    mktime = time.mktime((y, mo, d, h, m, s, wd, None))

    mktime += utc_offset * 3600

    y, mo, d, h, m, s, _, _ = time.localtime(mktime)

    rtc.datetime((y, mo, d, wd, h, m, s, ss))
