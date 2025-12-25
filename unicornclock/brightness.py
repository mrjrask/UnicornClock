import uasyncio as asyncio

# Todo:
# - Change the brightness smoothly

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def mapval(value, in_min, in_max, out_min, out_max):
    return (
        (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    )


class Brightness:

    MODE_AUTO = 0
    MODE_MANUAL = 1

    mode = MODE_AUTO
    level = 50
    offset = 0
    smooth_factor = 0.2
    min_level = 0
    max_level = 100
    min_offset = -100

    def __init__(
            self,
            galactic,
            level=50,
            mode=MODE_AUTO,
            offset=20,
            smooth_factor=0.2,
            min_level=0,
            max_level=100,
            min_offset=-100,
        ):
        self.galactic = galactic
        self.level = level
        self.mode = mode
        self.offset = offset
        self.auto_level = None
        self.smooth_factor = smooth_factor
        self.min_level = min_level
        self.max_level = max_level
        self.min_offset = min_offset

    def export(self):
        return {
            'mode': 'manual',
            'level': self.level,
            'current': self.galactic.get_brightness(),
        } if self.mode == self.MODE_MANUAL else {
            'mode': 'auto',
            'level': self.get_auto_level(),
            'offset': self.offset,
            'current': self.galactic.get_brightness(),
        }

    def get_corrected_level(self, level):
        return mapval(level, 0, 100, 0, 1)

    def get_auto_level(self):
        return mapval(self.galactic.light(), 0, 4095, 1, 100)

    def update(self):
        if self.mode == self.MODE_MANUAL:
            value = self.level
        else:
            raw_auto_level = self.get_auto_level()
            if self.auto_level is None:
                self.auto_level = raw_auto_level
            else:
                self.auto_level = (
                    self.auto_level * (1 - self.smooth_factor)
                    + raw_auto_level * self.smooth_factor
                )

            value = self.auto_level

        corrected = self.get_corrected_level(
            clamp(value + self.offset, self.min_level, self.max_level)
        )
        self.galactic.set_brightness(
            corrected
        )

    def set_mode(self, mode, offset=0):
        """Set the brightness mode
        `mode` is MODE_AUTO or MODE_MANUAL
        """
        self.mode = mode
        self.offset = offset

    def set_level(self, level):
        """Set the brightness level
        `level` need to be integer between 0 and 100
        """
        self.level = level

    def adjust(self, value):
        """Adjust the brightness
        `level` need to be integer between 0 and 100
        """
        if self.mode == self.MODE_MANUAL:
            self.level = clamp(self.level + value, self.min_level, self.max_level)
        else:
            self.offset = clamp(
                self.offset + value, self.min_offset, self.max_level
            )

    async def run(self):
        while True:
            self.update()
            await asyncio.sleep(1)