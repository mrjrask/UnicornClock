import json
import machine
import network
import random
import time
import ntptime
import uasyncio as asyncio
from galactic import GalacticUnicorn
from machine import Pin
from picographics import DISPLAY_GALACTIC_UNICORN, PicoGraphics

from unicornclock import Brightness, Clock, Position
from unicornclock.effects import (
    CharacterSlideDownEffect,
    HourlyColorCycleEffect,
    RainbowCharEffect,
    RainbowPixelEffect,
    RainbowMoveEffect,
    SolidMoveEffect,
)
from unicornclock.fontdriver import FontDriver
from unicornclock.fonts import default as default_font
from unicornclock.utils import debounce, set_time
from unicornclock.widgets import Calendar


try:
    from secrets import WLAN_SSID, WLAN_PASSWORD
except ImportError:
    print("Create secrets.py with WLAN_SSID and WLAN_PASSWORD information.")
    raise

# overclock to 200Mhz
machine.freq(200000000)

# create galactic object and graphics surface for drawing
galactic = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY_GALACTIC_UNICORN)

BLACK = graphics.create_pen(0, 0, 0)
BLUE = graphics.create_pen(0, 0, 255)
GREEN = graphics.create_pen(0, 255, 0)
GREY = graphics.create_pen(100, 100, 100)
ORANGE = graphics.create_pen(255, 128, 0)
PURPLE = graphics.create_pen(128, 0, 255)
RED = graphics.create_pen(255, 0, 0)
WHITE = graphics.create_pen(255, 255, 255)
YELLOW = graphics.create_pen(255, 255, 0)


SETTINGS_FILE = 'demo.json'
SHT41_ADDRESS = 0x44


class SHT41Sensor:
    def __init__(self, i2c, address=SHT41_ADDRESS):
        self.i2c = i2c
        self.address = address

    @staticmethod
    def _crc_ok(data, checksum):
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x31) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc == checksum

    def read_temperature_c(self):
        try:
            self.i2c.writeto(self.address, b'\xFD')
            time.sleep_ms(10)
            data = self.i2c.readfrom(self.address, 6)
        except OSError:
            return None

        if len(data) != 6:
            return None

        if not self._crc_ok(data[0:2], data[2]):
            return None

        raw_temp = (data[0] << 8) | data[1]
        return -45 + 175 * raw_temp / 65535


class AdafruitSHT41Sensor:
    def __init__(self, sht):
        self.sht = sht

    def read_temperature_c(self):
        try:
            return self.sht.temperature
        except OSError:
            return None


def init_sht41():
    i2c = machine.I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
    try:
        devices = i2c.scan()
    except OSError:
        return None

    if SHT41_ADDRESS not in devices:
        return None

    try:
        import adafruit_sht4x
    except ImportError:
        return SHT41Sensor(i2c)

    return AdafruitSHT41Sensor(adafruit_sht4x.SHT4x(i2c))


class TemperatureDisplay(FontDriver):
    def __init__(self, galactic, graphics, font_color, background_color):
        super().__init__(galactic, graphics, default_font)
        self.font_color = font_color
        self.background_color = background_color
        self.screen_width, self.screen_height = graphics.get_bounds()

    def _text_width(self, text):
        width = 0
        for _, offset, size in self.get_chars_bounds(text):
            width = offset + size
        return width

    def draw_temperature(self, temp_f):
        text = '{:.1f}F'.format(temp_f)
        text_width = self._text_width(text)
        x = max(0, (self.screen_width - text_width) // 2)

        self.graphics.set_pen(self.background_color)
        self.graphics.clear()
        self.graphics.set_pen(self.font_color)
        self.write_text(text, x, 0)
        self.galactic.update(self.graphics)

    async def run(self, sensor):
        while True:
            temperature_c = sensor.read_temperature_c()
            if temperature_c is not None:
                temperature_f = temperature_c * 9 / 5 + 32
                self.draw_temperature(temperature_f)

            wait_seconds = random.randint(240, 540)
            await asyncio.sleep(wait_seconds)


def central_utc_offset():
    """Return the US Central UTC offset (-6 standard, -5 daylight saving).

    Rules used (kept inline to avoid annual maintenance):
    - DST starts at 2:00 a.m. local standard time on the second Sunday in March
      (08:00 UTC because CST is UTC-6 before the switch).
    - DST ends at 2:00 a.m. local daylight time on the first Sunday in November
      (07:00 UTC because CDT is UTC-5 before the switch back to standard time).
    """

    def nth_weekday(year, month, weekday, n):
        first_day = time.mktime((year, month, 1, 0, 0, 0, 0, 0))
        first_weekday = time.gmtime(first_day)[6]
        days_until_weekday = (weekday - first_weekday) % 7
        day = 1 + days_until_weekday + 7 * (n - 1)
        return time.mktime((year, month, day, 0, 0, 0, 0, 0))

    # Ensure we have an accurate UTC time for the comparison.
    ntptime.settime()

    current_utc = time.time()
    year = time.gmtime(current_utc)[0]

    dst_start = nth_weekday(year, 3, 6, 2) + 8 * 3600  # second Sunday in March, 08:00 UTC
    dst_end = nth_weekday(year, 11, 6, 1) + 7 * 3600  # first Sunday in November, 07:00 UTC

    return -5 if dst_start <= current_utc < dst_end else -6


def wlan_connection():
    """WLAN connection

    During the connection, a colored progress is displayed.

    Color signification:
    - RED: Starting the connection
    - BLUE: Waiting for WLAN connection
    - ORANGE: Waiting for NTP update
    - GREEN: Done
    """
    width, height = graphics.get_bounds()

    x = 0
    def wait(color):
        nonlocal x
        graphics.set_pen(color)
        graphics.rectangle(x, 0, 2, height)
        galactic.update(graphics)
        x += 2
        if x >= width:
            x = 0
            graphics.set_pen(BLACK)
            graphics.clear()

    wait(RED)

    sta_if = network.WLAN(network.STA_IF)

    if not sta_if.isconnected():
        print('Connecting to %s network...' % WLAN_SSID)
        sta_if.active(True)
        sta_if.connect(WLAN_SSID, WLAN_PASSWORD)

        while not sta_if.isconnected():
            wait(BLUE)
            time.sleep(0.25)

    print('Connected to %s network' % WLAN_SSID)
    print('Network config:', sta_if.ifconfig())

    wait(ORANGE)

    set_time(central_utc_offset())

    wait(GREEN)

    graphics.set_pen(BLACK)
    graphics.clear()


class NoSpaceClock(Clock):
    space_between_char = lambda _, index, char: 1 if index in (0, 3, 6) else 0


class SimpleClock(NoSpaceClock):

    def callback_write_char(self, char, index):
        if self.handle_hour_tens_off(char, index):
            return
        colors = [
            GREY, WHITE,
            RED,
            GREY, WHITE,
            RED,
            GREY, WHITE,
        ]
        graphics.set_pen(colors[index])


class RainbowCharEffectClock(
    RainbowCharEffect,
    CharacterSlideDownEffect,
    NoSpaceClock,
):
    pass


class RainbowPixelEffectClock(
    RainbowPixelEffect,
    CharacterSlideDownEffect,
    NoSpaceClock,
):
    pass


class RainbowMoveEffectClock(RainbowMoveEffect, NoSpaceClock):
    pass


class SolidColorMoveEffectClock(SolidMoveEffect, NoSpaceClock):
    separator_color = WHITE

    def callback_write_char(self, char, index):
        if self.handle_hour_tens_off(char, index):
            return
        if char == ':':
            graphics.set_pen(self.separator_color)
        else:
            graphics.set_pen(self.font_color)


class RedMoveEffectClock(SolidColorMoveEffectClock):
    font_color = RED


class OrangeMoveEffectClock(SolidColorMoveEffectClock):
    font_color = ORANGE


class YellowMoveEffectClock(SolidColorMoveEffectClock):
    font_color = YELLOW


class GreenMoveEffectClock(SolidColorMoveEffectClock):
    font_color = GREEN


class BlueMoveEffectClock(SolidColorMoveEffectClock):
    font_color = BLUE


class PurpleMoveEffectClock(SolidColorMoveEffectClock):
    font_color = PURPLE


class HourlyColorCycleEffectClock(HourlyColorCycleEffect, NoSpaceClock):
    pass


effects = [
    SimpleClock,
    RainbowCharEffectClock,
    RainbowPixelEffectClock,
    RainbowMoveEffectClock,
    RedMoveEffectClock,
    OrangeMoveEffectClock,
    YellowMoveEffectClock,
    GreenMoveEffectClock,
    BlueMoveEffectClock,
    PurpleMoveEffectClock,
    HourlyColorCycleEffectClock,
]

clock = None

async def load_example(effect_index, **kwargs):
    global clock

    if clock:
        clock.is_running = False

    graphics.remove_clip()
    graphics.set_pen(BLACK)
    graphics.clear()

    default_kwargs = {
        'x': Position.RIGHT,
        'show_seconds': True,
        'am_pm_mode': am_pm_mode,
    }

    if kwargs:
        default_kwargs.update(kwargs)

    clock = effects[effect_index](
        galactic,
        graphics,
        **default_kwargs,
    )

    asyncio.create_task(clock.run())

mode = 0
effect = 0
am_pm_mode = False

try:
    print('Restoring the settings...', end='')
    with open(SETTINGS_FILE, 'r') as f:
        d = json.loads(f.read())
except (OSError, ValueError):
    print('[ERROR]')
else:
    mode = d.get('mode', 0)
    effect = d.get('effect', 0)
    am_pm_mode = d.get('am_pm_mode', False)
    print('[OK]')


async def buttons_handler(brightness, calendar, update_calendar):
    clock_kwargs = {}

    def log_brightness(action):
        print(
            '%s (brightness %.2f, light %d)' % (
                action,
                brightness.galactic.get_brightness(),
                brightness.galactic.light(),
            )
        )

    @debounce()
    def switch_mode(p):
        global mode
        mode = (mode + 1) % 4

    @debounce()
    def switch_effect(p):
        global effect
        effect = (effect + 1) % len(effects)

    @debounce()
    def brightness_down(p):
        if brightness.is_auto():
            print('Lux buttons disabled while auto brightness is enabled')
            return
        brightness.adjust(-5)
        brightness.update()
        log_brightness('Lux - pressed')

    @debounce()
    def brightness_up(p):
        if brightness.is_auto():
            print('Lux buttons disabled while auto brightness is enabled')
            return
        brightness.adjust(5)
        brightness.update()
        log_brightness('Lux + pressed')

    @debounce()
    def toggle_am_pm(p):
        global am_pm_mode
        am_pm_mode = not am_pm_mode

    @debounce()
    def toggle_auto_brightness(p):
        brightness.toggle_mode()
        brightness.update(log_light=brightness.is_auto())

    Pin(GalacticUnicorn.SWITCH_A, Pin.IN, Pin.PULL_UP) \
        .irq(trigger=Pin.IRQ_FALLING, handler=switch_mode)

    Pin(GalacticUnicorn.SWITCH_B, Pin.IN, Pin.PULL_UP) \
        .irq(trigger=Pin.IRQ_FALLING, handler=switch_effect)

    Pin(GalacticUnicorn.SWITCH_C, Pin.IN, Pin.PULL_UP) \
        .irq(trigger=Pin.IRQ_FALLING, handler=toggle_am_pm)

    Pin(GalacticUnicorn.SWITCH_D, Pin.IN, Pin.PULL_UP) \
        .irq(trigger=Pin.IRQ_FALLING, handler=toggle_auto_brightness)

    Pin(GalacticUnicorn.SWITCH_BRIGHTNESS_DOWN, Pin.IN, Pin.PULL_UP) \
        .irq(trigger=Pin.IRQ_FALLING, handler=brightness_down)

    Pin(GalacticUnicorn.SWITCH_BRIGHTNESS_UP, Pin.IN, Pin.PULL_UP) \
        .irq(trigger=Pin.IRQ_FALLING, handler=brightness_up)

    async def load_current_example():
        nonlocal current_effect, current_mode, current_am_pm

        print('Change (mode %i, effect %i)' % (mode, effect))

        if mode == 0:
            calendar.set_position(Position.LEFT)
            clock_kwargs = {
                'x': Position.RIGHT,
                'callback_hour_change': update_calendar,
            }
        elif mode == 1:
            calendar.set_position(Position.RIGHT)
            clock_kwargs = {
                'x': Position.LEFT,
                'callback_hour_change': update_calendar,
            }
        elif mode == 2:
            clock_kwargs = {
                'x': Position.CENTER,
                'callback_hour_change': None,
                'space_between_char': 2,
            }
        elif mode == 3:
            clock_kwargs = {
                'show_seconds': False,
                'x': Position.CENTER,
                'callback_hour_change': None,
                'space_between_char': 2,
            }

        await load_example(effect, **clock_kwargs)

        current_mode = mode
        current_effect = effect
        current_am_pm = am_pm_mode

    current_effect = 0
    current_mode = 0
    current_am_pm = am_pm_mode

    await load_current_example()

    last_change_time = None
    while True:
        if (mode != current_mode or effect != current_effect or
                am_pm_mode != current_am_pm):
            await load_current_example()

            last_change_time = time.time()

        if last_change_time and last_change_time + 5 < time.time():
            print('Saving the settings file')
            with open(SETTINGS_FILE, 'w') as f:
                f.write(json.dumps({
                    'mode': mode,
                    'effect': effect,
                    'am_pm_mode': am_pm_mode,
                }))

            last_change_time = None

        await asyncio.sleep(0.25)


async def example():
    brightness = Brightness(galactic)
    brightness.update()
    print('Default brightness at launch: %.2f' % brightness.galactic.get_brightness())

    wlan_connection()

    sensor = init_sht41()
    if sensor:
        temperature_c = sensor.read_temperature_c()
        if temperature_c is None:
            print('SHT41 detected but no data, falling back to clock.')
            sensor = None
        else:
            print('SHT41 detected on Stemma QT, displaying temperature.')
            temp_display = TemperatureDisplay(galactic, graphics, WHITE, BLACK)
            asyncio.create_task(brightness.run())
            asyncio.create_task(temp_display.run(sensor))
            return

    calendar = Calendar(galactic, graphics)

    def update_calendar(*args):
        calendar.draw_all()

    asyncio.create_task(brightness.run())
    asyncio.create_task(buttons_handler(brightness, calendar, update_calendar))

    await load_example(0, callback_hour_change=update_calendar)


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(example())
    loop.run_forever()


if __name__ == '__main__':
    main()
