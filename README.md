# UnicornClock

UnicornClock is a MicroPython clock and calendar demo for the Pimoroni Galactic Unicorn. It pairs animated clock effects with an optional calendar widget, automatic or manual brightness control, Wi-Fi time synchronisation, and simple configuration you can tweak directly on the device.

![Unicorn Clock Example](demo.gif)

[Example video](https://www.youtube.com/watch?v=Gvnccr2_wY0)

## Features

* NTP-backed time with helper utilities for setting timezone offsets.
* Multiple clock effects, including per-character colour ramps and pixel-based animations.
* Calendar widget that draws a dated calendar frame alongside the clock.
* Adjustable clock position (left, right, or centred) and configurable spacing between characters.
* 12/24-hour toggle, optional seconds display, and palette control for fonts and backgrounds.
* Automatic brightness tied to the Galactic Unicorn light sensor with on-device offsets, or manual brightness control.
* Persisted settings (`demo.json`) for the current layout, effect, and AM/PM mode.
* Easily hackable font and effect system so you can extend characters, backgrounds, and animations.

## Compatibility

- Pimoroni Galactic Unicorn (tested)
- Work in progress for the Pimoroni Cosmic Unicorn

## Installation

1. Copy the repository files to your device (for example with [Thonny](https://thonny.org/)).
2. Create a `secrets.py` file with your network credentials:

   ```python
   WLAN_SSID = "Your WLAN SSID"
   WLAN_PASSWORD = "Your secrets password"
   ```

3. If you need a different timezone, adjust the `central_utc_offset()` helper in `example.py` or call `set_time()` from `unicornclock.utils` with the appropriate offset.

## Running the example

The example combines the clock and calendar widgets, synchronises time over Wi-Fi, and exposes on-device controls:

* Button A: switch between layouts (calendar left/right, centred clock with and without seconds).
* Button B: cycle through the bundled clock effects.
* Button C: toggle 12/24-hour display.
* Brightness buttons: raise or lower brightness (affects the auto-brightness offset in automatic mode).

Settings are saved to `demo.json` after five seconds without further changes so your preferred layout, effect, and hour mode persist across reboots.

To run the demo on the device, execute `main.py` (which forwards to `example.py`).

## Library usage

You can reuse the clock and brightness helpers in your own program. A minimal example that shows a moving rainbow clock is below:

```python
import uasyncio as asyncio
from galactic import GalacticUnicorn
from picographics import DISPLAY_GALACTIC_UNICORN, PicoGraphics

from unicornclock import Brightness, Clock, Position
from unicornclock.effects import RainbowMoveEffect

# Create hardware objects
unicorn = GalacticUnicorn()
graphics = PicoGraphics(DISPLAY_GALACTIC_UNICORN)

class RainbowClock(RainbowMoveEffect, Clock):
    pass

async def main():
    brightness = Brightness(unicorn, offset=20)
    clock = RainbowClock(
        unicorn,
        graphics,
        x=Position.CENTER,
        show_seconds=True,
    )

    asyncio.create_task(brightness.run())
    asyncio.create_task(clock.run())

    # Keep the tasks alive
    while True:
        await asyncio.sleep(1)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_forever()
```

Explore `unicornclock/effects.py` for more effect mixins and `unicornclock/widgets.py` for the calendar widget you can pair with the clock.

## Contribute

* Code must respect `flake8` and `isort`.
* Format commits with [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
