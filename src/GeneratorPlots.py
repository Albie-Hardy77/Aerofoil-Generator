import math

import numpy as np

import Styles
from Annotations import draw_annotations
from AerofoilGeometryMaths import tip_section


class GeneratorPlots:
    """The 2D and 3D drawing for the generator window. Mixed into GeneratorWindow, so it uses the window's
    figure (fig, ax_2d, ax_3d, canvas), profile coordinates (xu, yu, xl, yl) and view settings directly."""

    def clear_grid_note(self):
        if self.grid_note is not None:
            self.grid_note.remove()
            self.grid_note = None

    def redraw(self):
        if not self.has_profile or not self.is_3d:
            self.clear_grid_note()

        if not self.has_profile:
            self.ax_2d.clear()
            self.ax_3d.clear()
            self.style_2d_axes()
            self.style_3d_axes()
            self.canvas.draw()
        elif self.is_3d:
            self.plot_3d()
        else:
            self.update_2d_rotation(self.angle_of_attack_slider.value())

    def style_2d_axes(self):
        self.fig.patch.set_facecolor(Styles.PANEL)
        self.ax_2d.set_position([0, 0, 1, 1])
        self.ax_2d.set_axis_off()

    def style_3d_axes(self):
        self.fig.patch.set_facecolor(Styles.PANEL)
        self.ax_3d.set_position([0, 0, 1, 1])
        self.ax_3d.set_axis_off()
        self.ax_3d.patch.set_alpha(0.0)

    def update_2d_rotation(self, angle_degree):
        angle_rad = math.radians(-angle_degree)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)

        xu_rotated = self.xu * cos_a - self.yu * sin_a
        yu_rotated = self.xu * sin_a + self.yu * cos_a

        xl_rotated = self.xl * cos_a - self.yl * sin_a
        yl_rotated = self.xl * sin_a + self.yl * cos_a

        self.plot_2d(xu_rotated, yu_rotated, xl_rotated, yl_rotated, angle_degree)

    def plot_2d(self, xu, yu, xl, yl, angle_degree=0):
        self.clear_grid_note()
        self.ax_2d.clear()
        self.style_2d_axes()

        self.ax_2d.plot(xu, yu, color=Styles.TEXT, zorder=2)
        self.ax_2d.plot(xl, yl, color=Styles.TEXT, zorder=2)
        self.ax_2d.set_aspect("equal", adjustable="datalim")

        if self.comparison is not None:
            angle = math.radians(-angle_degree)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            for cx, cy in zip(*[iter(self.comparison.calculate_coordinates())] * 2):
                self.ax_2d.plot(cx * cos_a - cy * sin_a, cx * sin_a + cy * cos_a, color=Styles.PINK,
                                linestyle="--", linewidth=1.5, zorder=2)
            self.ax_2d.text(0.015, 0.965, f"Comparing: {self.comparison.display_name}", transform=self.ax_2d.transAxes,
                            color=Styles.PINK, fontsize=9, fontweight="bold", va="top", fontfamily=["Arial", "DejaVu Sans"])

        if self.annotations_on:
            draw_annotations(self.ax_2d, self.PlotMaths, self.xu, self.yu, self.xl, self.yl, angle_degree)
        elif self.grid_on:
            xs, ys = [xu, xl], [yu, yl]
            if self.comparison is not None:
                angle = math.radians(-angle_degree)
                for cx, cy in zip(*[iter(self.comparison.calculate_coordinates())] * 2):
                    xs.append(cx * math.cos(angle) - cy * math.sin(angle))
                    ys.append(cx * math.sin(angle) + cy * math.cos(angle))
            self.fit_view_2d(xs, ys)

        if self.grid_on:
            self.draw_scale_grid_2d()

        self.canvas.draw()

    @staticmethod
    def nice_grid_step(range_mm):
        # The smallest round spacing that gives no more than about 14 lines across the view
        for step in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
            if range_mm / step <= 14:
                return step

        return 1000

    def fit_view_2d(self, xs, ys):
        xmin, xmax = min(np.min(a) for a in xs), max(np.max(a) for a in xs)
        ymin, ymax = min(np.min(a) for a in ys), max(np.max(a) for a in ys)
        pad = 0.14 * max(xmax - xmin, ymax - ymin)

        box = self.ax_2d.get_window_extent()
        ratio = box.width / box.height
        centre_x, centre_y = (xmin + xmax) / 2, (ymin + ymax) / 2
        width = max(xmax - xmin + 2 * pad, (ymax - ymin + 2 * pad) * ratio)
        height = width / ratio

        self.ax_2d.set_aspect("equal", adjustable="box")
        self.ax_2d.set_xlim(centre_x - width / 2, centre_x + width / 2)
        self.ax_2d.set_ylim(centre_y - height / 2, centre_y + height / 2)

    def draw_scale_grid_2d(self):
        """Faint millimetre grid in real units (the root chord is chord_mm long) with tick marks and labels."""
        ax = self.ax_2d
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()

        step_mm = self.nice_grid_step(max(x1 - x0, y1 - y0) * self.chord_mm)
        step = step_mm / self.chord_mm
        tick = 0.018 * (y1 - y0)
        font = ["Arial", "DejaVu Sans"]

        ax.set_autoscale_on(False)

        for k in range(math.ceil(x0 / step), math.floor(x1 / step) + 1):
            x = k * step
            major = k % 5 == 0
            ax.plot([x, x], [y0, y1], color=Styles.GREY, linewidth=1.0 if major else 0.6, alpha=0.6 if major else 0.3, zorder=1)
            ax.plot([x, x], [y0, y0 + tick], color=Styles.LIGHT_GREY, linewidth=1.2, zorder=1)
            ax.text(x, y0 + tick * 1.5, f"{k * step_mm:g}", ha="center", va="bottom", fontsize=7,
                    color=Styles.LIGHT_GREY, fontfamily=font, zorder=1)

        for k in range(math.ceil(y0 / step), math.floor(y1 / step) + 1):
            y = k * step
            major = k % 5 == 0
            ax.plot([x0, x1], [y, y], color=Styles.GREY, linewidth=1.0 if major else 0.6, alpha=0.6 if major else 0.3, zorder=1)
            ax.plot([x0, x0 + tick * ((x1 - x0) / (y1 - y0))], [y, y], color=Styles.LIGHT_GREY, linewidth=1.2, zorder=1)
            ax.text(x0 + tick * 1.5 * ((x1 - x0) / (y1 - y0)), y, f"{k * step_mm:g}", ha="left", va="center", fontsize=7,
                    color=Styles.LIGHT_GREY, fontfamily=font, zorder=1)

        ax.text(0.985, 0.97, f"Grid: {step_mm:g} mm", transform=ax.transAxes, ha="right", va="top", fontsize=8,
                color=Styles.LIGHT_GREY, fontweight="bold", fontfamily=font, zorder=1)

    def draw_scale_grid_3d(self, span, tip_xs, tip_ys):
        """Millimetre grid on the root plane plus a ruler along the span, in real units."""
        ax = self.ax_3d
        xs = np.concatenate([self.xu, self.xl, tip_xs[0], tip_xs[1]])
        ys = np.concatenate([self.yu, self.yl, tip_ys[0], tip_ys[1]])
        margin = 0.1

        step_mm = self.nice_grid_step((xs.max() - xs.min() + 2 * margin) * self.chord_mm)
        step = step_mm / self.chord_mm
        x0, x1 = math.floor((xs.min() - margin) / step) * step, math.ceil((xs.max() + margin) / step) * step
        half = max(abs(ys.min()), abs(ys.max())) + margin
        y0, y1 = -math.ceil(half / step) * step, math.ceil(half / step) * step
        font = dict(fontsize=7, color=Styles.LIGHT_GREY, fontweight="bold")
        tick = 0.012
        self.grid_extent_3d = (x0, x1, y0, y1)

        for k in range(round(x0 / step), round(x1 / step) + 1):
            x = k * step
            ax.plot([x, x], [y0, y1], [0, 0], color=Styles.GREY, linewidth=0.7, alpha=0.5)
            ax.plot([x, x], [y0, y0 + tick * 3], [0, 0], color=Styles.LIGHT_GREY, linewidth=1.0)
            ax.text(x, y0 - tick * 4, 0, f"{k * step_mm:g}", ha="center", va="top", **font)

        for k in range(round(y0 / step), round(y1 / step) + 1):
            y = k * step
            ax.plot([x0, x1], [y, y], [0, 0], color=Styles.GREY, linewidth=0.7, alpha=0.5)
            ax.plot([x0, x0 + tick * 3], [y, y], [0, 0], color=Styles.LIGHT_GREY, linewidth=1.0)

        # Ruler along the span, beside the root section
        ax.plot([x0, x0], [y0, y0], [0, span], color=Styles.LIGHT_GREY, linewidth=1.2)
        for k in range(0, math.floor(span / step) + 1):
            ax.plot([x0, x0 + tick * 3], [y0, y0], [k * step, k * step], color=Styles.LIGHT_GREY, linewidth=1.0)

        ax.text(x0 - tick * 2, y0, span, f"{self.span_mm:g} mm", ha="right", va="bottom", **font)

        self.grid_step_3d = step_mm

    def plot_3d(self):
        self.clear_grid_note()
        self.ax_2d.clear()
        self.style_2d_axes()

        self.ax_3d.clear()
        self.style_3d_axes()

        span = self.span_mm / self.chord_mm
        tip_chord = self.tip_chord_mm / self.chord_mm
        tip_xu, tip_yu = tip_section(self.xu, self.yu, 1.0, tip_chord, span, self.sweep_deg, self.twist_deg)
        tip_xl, tip_yl = tip_section(self.xl, self.yl, 1.0, tip_chord, span, self.sweep_deg, self.twist_deg)

        z_front = np.zeros(len(self.xu))
        z_back = np.full(len(self.xu), span)

        self.ax_3d.plot(self.xu, self.yu, z_front, color=Styles.TEXT)
        self.ax_3d.plot(self.xl, self.yl, z_front, color=Styles.TEXT)
        self.ax_3d.plot(tip_xu, tip_yu, z_back, color=Styles.TEXT)
        self.ax_3d.plot(tip_xl, tip_yl, z_back, color=Styles.TEXT)

        wire_indices = np.linspace(0, len(self.xu) - 1, self.wire_counts_3d[self.wire_count_index]).round().astype(int)

        for i in wire_indices:
            self.ax_3d.plot([self.xu[i], tip_xu[i]], [self.yu[i], tip_yu[i]], [0.0, span], color=Styles.TEXT)
            self.ax_3d.plot([self.xl[i], tip_xl[i]], [self.yl[i], tip_yl[i]], [0.0, span], color=Styles.TEXT)

        self.grid_extent_3d = None
        if self.grid_on:
            self.draw_scale_grid_3d(span, (tip_xu, tip_xl), (tip_yu, tip_yl))

        # Centre the scene in a cube so zooming keeps it in the middle of the frame
        x_all = np.concatenate([self.xu, self.xl, tip_xu, tip_xl])
        y_all = np.concatenate([self.yu, self.yl, tip_yu, tip_yl])
        x_min, x_max, y_min, y_max = x_all.min(), x_all.max(), y_all.min(), y_all.max()
        if self.grid_extent_3d is not None:
            x_min, x_max = min(x_min, self.grid_extent_3d[0]), max(x_max, self.grid_extent_3d[1])
            y_min, y_max = min(y_min, self.grid_extent_3d[2]), max(y_max, self.grid_extent_3d[3])

        radius = 0.51 * max(x_max - x_min, y_max - y_min, span)
        self.ax_3d.set_xlim3d((x_min + x_max) / 2 - radius, (x_min + x_max) / 2 + radius)
        self.ax_3d.set_ylim3d((y_min + y_max) / 2 - radius, (y_min + y_max) / 2 + radius)
        self.ax_3d.set_zlim3d(span / 2 - radius, span / 2 + radius)
        self.ax_3d.view_init(elev=100, azim=-95, roll=0, vertical_axis='z')

        # matplotlib draws the 3D scene inside a square and clips to it. Turn that clipping off so the
        # frame itself is the only window, then zoom until the drawing fills the frame.
        for artist in list(self.ax_3d.lines) + list(self.ax_3d.texts):
            artist.set_clip_on(False)

        # Measure the drawing, centre it and zoom to fit, a few times over: matplotlib's zoom isn't exactly
        # proportional, and anything past the canvas edge isn't in the image to be measured
        zoom = 1.0
        self.offset_3d = (0.0, 0.0)
        for _ in range(12):
            self.set_zoom_3d(zoom)
            self.canvas.draw()
            bounds = self.content_bounds()
            if bounds is None:
                break

            # The drawing is rarely centred (a long swept wing leans to one side), so keep track of how far its
            # middle is from the middle of the canvas per unit of zoom, as a fraction of the canvas. A clipped
            # drawing still gives the right direction to move in.
            drawing_width, drawing_height, touches_edge, x_offset, y_offset = bounds
            height, width = np.asarray(self.canvas.buffer_rgba()).shape[:2]
            dx, dy = self.offset_3d
            self.offset_3d = (dx + x_offset / zoom / width, dy + y_offset / zoom / height)

            if touches_edge:
                zoom = max(zoom * 0.8, 0.05)
                continue

            scale = min(0.92 * width / drawing_width, 0.9 * height / drawing_height)
            if abs(scale - 1) < 0.02 and abs(x_offset) < 3 and abs(y_offset) < 3:
                break
            zoom = float(np.clip(zoom * scale, 0.05, 8.0))

        self.base_zoom_3d = zoom
        self.set_zoom_3d(zoom * self.view_zoom)

        if self.grid_note is not None:
            self.grid_note.remove()
            self.grid_note = None
        if self.grid_on:
            self.grid_note = self.fig.text(0.985, 0.03, f"Grid: {self.grid_step_3d:g} mm  ·  semi-span {self.span_mm:g} mm",
                                           ha="right", va="bottom", fontsize=8, color=Styles.LIGHT_GREY, fontweight="bold")

        self.canvas.draw()

    def scroll_zoom_3d(self, event):
        """Mouse wheel over the plot zooms the 3D model in and out."""
        if not (self.is_3d and self.has_profile) or event.step == 0:
            return

        self.view_zoom = float(np.clip(self.view_zoom * 1.15 ** event.step, 0.25, 10.0))
        self.set_zoom_3d(self.base_zoom_3d * self.view_zoom)
        self.canvas.draw_idle()

    def set_zoom_3d(self, zoom):
        """Zooms the 3D scene about its own middle: matplotlib zooms about the middle of the axes, so the axes
        are shifted by the drawing's offset (which grows with the zoom) to keep the drawing centred."""
        dx, dy = self.offset_3d
        self.ax_3d.set_box_aspect((1, 1, 1), zoom=zoom)
        self.ax_3d.set_position([-dx * zoom, dy * zoom, 1, 1])

    def content_bounds(self):
        """(width, height, touches_edge, x offset, y offset) in pixels of everything drawn on the canvas that isn't
        the background. The offsets are from the middle of the canvas to the middle of the drawing (y downwards)."""
        image = np.asarray(self.canvas.buffer_rgba())
        background = np.array([int(Styles.PANEL[i:i + 2], 16) for i in (1, 3, 5)])
        mask = np.abs(image[:, :, :3].astype(int) - background).max(axis=2) > 12
        rows, columns = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]

        if len(rows) == 0:
            return None

        touches_edge = rows[0] == 0 or columns[0] == 0 or rows[-1] == mask.shape[0] - 1 or columns[-1] == mask.shape[1] - 1

        x_offset = (columns[0] + columns[-1]) / 2 - (mask.shape[1] - 1) / 2
        y_offset = (rows[0] + rows[-1]) / 2 - (mask.shape[0] - 1) / 2

        return columns[-1] - columns[0] + 1, rows[-1] - rows[0] + 1, touches_edge, x_offset, y_offset
