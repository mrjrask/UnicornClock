import random
from time import sleep

from .common import Clip
from .utils import from_hsv


class CharacterSlideEffect:
    """Character slide effect"""

    # True: Down, False: Up
    direction = 1

    async def update_time(self, time):
        if self.last_time is None:
            self.write_time(time)
            self.last_time = time

        _, HEIGHT = self.graphics.get_bounds()

        y = self.y
        if not self.direction:
            y += HEIGHT + 1

        for i in range(
            (HEIGHT * 2 if self.direction else HEIGHT + 1) + 1
        ):
            for index, offset, size, a, b in self.iter_on_changes(time):
                character = a if i <= HEIGHT else b

                with Clip(self.graphics, self.x + offset, 0, size, HEIGHT):
                    self.graphics.set_pen(self.background_color)
                    self.graphics.clear()

                    self.callback_write_char(character, index)
                    self.write_char(character, self.x + offset, y)

            self.galactic.update(self.graphics)

            if self.direction:
                y += 1
                if y >= HEIGHT:
                    y = -HEIGHT
            else:
                y -= 1

            sleep(0.01)

        self.last_time = time


class CharacterSlideDownEffect(CharacterSlideEffect):
    direction = True


class CharacterSlideUpEffect(CharacterSlideEffect):
    direction = False


class RainbowMixin:

    hue_offset = 0
    hue_map = []

    def callback_after_init(self):
        info = self.chars_bounds[-1]
        self.width = info[1] + info[2]
        self.hue_map = [
            from_hsv(x / self.width, 1.0, 1.0) for x in range(self.width)
        ]

        self.separator_color = self.graphics.create_pen(255, 255, 255)

    def set_pen(self, char, i):
        color = self.separator_color

        if char != ':':
            colour = self.hue_map[
                int((i + (self.hue_offset * self.width)) % self.width)
            ]
            color = self.graphics.create_pen(
                int(colour[0]), int(colour[1]), int(colour[2])
            )

        self.graphics.set_pen(color)


class RainbowCharEffect(RainbowMixin):
    """Rainbow Char Effect

    Each character color come from a rainbow.
    """

    def callback_write_char(self, char, index):
        if hasattr(self, "handle_hour_tens_off") and self.handle_hour_tens_off(char, index):
            return

        self.set_pen(char, index)


class RainbowPixelEffect(RainbowMixin):
    """Rainbow Pixel Effect

    Each pixel column color of character come from a rainbow.
    """

    def callback_set_pixel(self, char, x, y):
        if getattr(self, "_current_char_hidden", False):
            self.graphics.set_pen(self.background_color)
            return

        self.set_pen(char, x)


class RainbowMoveEffect(RainbowMixin):
    """Rainbow move effect

    Colorize the characters as a rainbow and move it.
    """

    loop_sleep = 0.01

    def callback_set_pixel(self, char, x, y):
        if getattr(self, "_current_char_hidden", False):
            self.graphics.set_pen(self.background_color)
            return

        self.set_pen(char, x)

    async def update_time(self, time):
        for index, (character, offset, size) in enumerate(
            self.get_chars_bounds(time)
        ):
            with Clip(self.graphics, self.x + offset, self.y, size,
                      self.screen_height):
                self.graphics.set_pen(self.background_color)
                self.graphics.clear()

                if self.callback_write_char:
                    self.callback_write_char(character, index)

                self.write_char(character, self.x + offset, self.y)

        self.galactic.update(self.graphics)

    async def callback_time_updated(self, hour, minute, second):
        self.hue_offset += 0.01

    async def need_update(self, hour, minute, second):
        return True


class SolidMoveEffect:
    """Solid move effect

    Redraw the characters at each update without changing their positions.
    """

    loop_sleep = 0.01

    async def update_time(self, time):
        for index, (character, offset, size) in enumerate(
            self.get_chars_bounds(time)
        ):
            with Clip(self.graphics, self.x + offset, self.y, size,
                      self.screen_height):
                self.graphics.set_pen(self.background_color)
                self.graphics.clear()

                if self.callback_write_char:
                    self.callback_write_char(character, index)

                self.write_char(character, self.x + offset, self.y)

        self.galactic.update(self.graphics)

    async def need_update(self, hour, minute, second):
        return True


class HourlyColorCycleEffect:
    """Hourly color cycle effect.

    Cycle through red, orange, yellow, green, blue, purple over one hour.
    """

    loop_sleep = 0.1

    _cycle_colors = (
        (255, 0, 0),
        (255, 128, 0),
        (255, 255, 0),
        (0, 255, 0),
        (0, 0, 255),
        (128, 0, 255),
    )

    def callback_after_init(self):
        self.separator_color = self.graphics.create_pen(255, 255, 255)
        self.current_color = self.graphics.create_pen(255, 0, 0)
        self._shuffle_cycle_colors()
        self.callback_hour_change = self._on_hour_change

    def _shuffle_cycle_colors(self):
        self._cycle_order = list(self._cycle_colors)
        random.shuffle(self._cycle_order)

    def _on_hour_change(self, hour):
        self._shuffle_cycle_colors()
        start = self._cycle_order[0]
        self.current_color = self.graphics.create_pen(
            start[0], start[1], start[2]
        )

    def _interpolate_channel(self, start, end, ratio):
        return int(start + (end - start) * ratio)

    def _get_cycle_color(self, hour, minute, second):
        seconds = (minute * 60) + second
        cycle_order = getattr(self, "_cycle_order", self._cycle_colors)
        segment_length = 3600 / len(cycle_order)
        segment = int(seconds // segment_length)
        ratio = (seconds % segment_length) / segment_length
        start = cycle_order[segment]
        end = cycle_order[(segment + 1) % len(cycle_order)]
        red = self._interpolate_channel(start[0], end[0], ratio)
        green = self._interpolate_channel(start[1], end[1], ratio)
        blue = self._interpolate_channel(start[2], end[2], ratio)
        return self.graphics.create_pen(red, green, blue)

    def callback_write_char(self, char, index):
        if self.handle_hour_tens_off(char, index):
            return

        if char == ':':
            self.graphics.set_pen(self.separator_color)
        else:
            self.graphics.set_pen(self.current_color)

    async def update_time(self, time):
        for index, (character, offset, size) in enumerate(
            self.get_chars_bounds(time)
        ):
            with Clip(self.graphics, self.x + offset, self.y, size,
                      self.screen_height):
                self.graphics.set_pen(self.background_color)
                self.graphics.clear()

                if self.callback_write_char:
                    self.callback_write_char(character, index)

                self.write_char(character, self.x + offset, self.y)

        self.galactic.update(self.graphics)

    async def need_update(self, hour, minute, second):
        self.current_color = self._get_cycle_color(hour, minute, second)
        return second != self.last_second
