import uasyncio as asyncio


class Brightness:

    MODE_AUTO = 0
    MODE_MANUAL = 1

    mode = MODE_AUTO
    level = 50
    current_brightness = 0.0

    MIN_LIGHT = 14
    MAX_LIGHT = 19
    MIN_BRIGHTNESS = 0.06
    MAX_BRIGHTNESS = 0.36

    def __init__(
            self,
            galactic,
            level=50,
            mode=MODE_AUTO,
        ):
        self.galactic = galactic
        self.level = level
        self.mode = mode
        self.current_brightness = self.galactic.get_brightness()

    def export(self):
        return {
            'mode': 'manual',
            'level': self.level,
            'current': self.galactic.get_brightness(),
        } if self.mode == self.MODE_MANUAL else {
            'mode': 'auto',
            'level': self.get_target_brightness(),
            'current': self.galactic.get_brightness(),
        }

    def get_corrected_level(self, level):
        return max(0, min(1, level / 100))

    def get_target_brightness(self):
        if self.mode == self.MODE_MANUAL:
            return self.get_corrected_level(self.level)

        light_value = self.galactic.light()

        if light_value <= self.MIN_LIGHT:
            target = self.MIN_BRIGHTNESS
        elif light_value >= self.MAX_LIGHT:
            target = self.MAX_BRIGHTNESS
        else:
            span = self.MAX_LIGHT - self.MIN_LIGHT
            position = (light_value - self.MIN_LIGHT) / span
            target = self.MIN_BRIGHTNESS + (
                position * (self.MAX_BRIGHTNESS - self.MIN_BRIGHTNESS)
            )

        return max(0, min(1, target))

    def update(self, *, log_light=False):
        target = self.get_target_brightness()

        if self.mode == self.MODE_AUTO and log_light:
            print('Auto brightness: light %d -> target %.2f' % (
                self.galactic.light(), target
            ))

        # Smooth transition toward the target brightness.
        step = 0.02
        if target > self.current_brightness:
            self.current_brightness = min(target, self.current_brightness + step)
        else:
            self.current_brightness = max(target, self.current_brightness - step)

        self.galactic.set_brightness(
            self.current_brightness
        )

    def set_mode(self, mode):
        """Set the brightness mode
        `mode` is MODE_AUTO or MODE_MANUAL
        """
        self.mode = mode

    def toggle_mode(self):
        self.set_mode(self.MODE_MANUAL if self.mode == self.MODE_AUTO else self.MODE_AUTO)
        print('Auto brightness %s' % ('enabled' if self.is_auto() else 'disabled'))

    def is_auto(self):
        return self.mode == self.MODE_AUTO

    def set_level(self, level):
        """Set the brightness level
        `level` need to be integer between 0 and 100
        """
        self.level = level

    def adjust(self, value):
        """Adjust the brightness
        `level` need to be integer between 0 and 100
        """
        if self.is_auto():
            print('Lux buttons disabled while auto brightness is enabled')
            return

        self.level = max(0, min(100, self.level + value))
        self.current_brightness = self.get_corrected_level(self.level)
        self.galactic.set_brightness(self.current_brightness)

    async def run(self):
        while True:
            log_light = self.is_auto()
            self.update(log_light=log_light)
            await asyncio.sleep(0.25 if self.is_auto() else 1)
