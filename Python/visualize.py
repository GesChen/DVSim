import get_data
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import time

COLOR_MODE = "col"  # "col" or "bw"

res = (1280, 720)

(x, y, t, p) = get_data.load_umd_dataset(r'E:\DVSim\Python\data\from umd\events\sequence_haowen1_SIDE_DYNAMIC_DARK_bottle\proc\events')
# (x, y, t, p) = get_data.load_unity_dataset(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\camera 2\events.npz')
# (x, y, t, p) = get_data.load_v2e_dataset(r'E:\DVSim\Python\v2e-master\v2ecore\output\testout.npz')

(x, y, t, p) = get_data.sortdata(x, y, t, p)

if COLOR_MODE not in ("col", "bw"):
    raise ValueError('COLOR_MODE must be "col" or "bw"')

def event_colors():
    if COLOR_MODE == "col":
        return np.where(p == 1, "red", "blue")
    else:
        return np.where(p == 1, "white", "black")

def visualize_3d():
    print("loading 3d graph...")
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")

    ax.scatter(x, t, y, marker=".", c=event_colors(), s=1)
    ax.set_xlabel("x")
    ax.set_ylabel("t")
    ax.set_zlabel("y")

    plt.show()

playing = False

def visualize_slice():
    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.42)

    ax.set_xlim(0, res[0])
    ax.set_ylim(0, res[1])

    timeslice = t[0]
    tslicewidth = 0.01

    ax_time = plt.axes([0.25, 0.25, 0.65, 0.03])
    slider_slice = Slider(ax_time, "Time Slice", t.min(), t.max(), valinit=timeslice)

    ax_fine = plt.axes([0.25, 0.20, 0.65, 0.03])
    slider_fine = Slider(
        ax_fine,
        "Fine Offset",
        -tslicewidth / 2,
        tslicewidth / 2,
        valinit=0.0
    )

    ax_width = plt.axes([0.25, 0.15, 0.65, 0.03])
    slider_width = Slider(ax_width, "Slice Width", 0.0, .10, valinit=tslicewidth)

    ax_button = plt.axes([0.45, 0.05, 0.15, 0.06])
    button_play = Button(ax_button, "Play")

    img = np.zeros((res[1], res[0], 3), dtype=np.uint8)

    im = ax.imshow(img, origin="lower", interpolation="nearest")
    ax.set_axis_off()

    dt = 0.038

    def redraw(_=None):
        center_t = slider_slice.val + slider_fine.val
        width = slider_width.val

        lo = np.searchsorted(t, center_t - width / 2)
        hi = np.searchsorted(t, center_t + width / 2)

        xs = x[lo:hi]
        ys = y[lo:hi]
        ps = p[lo:hi]

        pos = ps == 1
        neg = ~pos

        if COLOR_MODE == "col":
            img.fill(0)
            img[ys[pos], xs[pos]] = [255, 0, 0]
            img[ys[neg], xs[neg]] = [0, 0, 255]
        else:
            img.fill(127)
            img[ys[pos], xs[pos]] = [255, 255, 255]
            img[ys[neg], xs[neg]] = [0, 0, 0]

        im.set_data(img)
        fig.canvas.draw_idle()

    def update_fine_range(_=None):
        width = slider_width.val
        slider_fine.valmin = -width / 2
        slider_fine.valmax = width / 2
        slider_fine.ax.set_xlim(slider_fine.valmin, slider_fine.valmax)

        if slider_fine.val < slider_fine.valmin:
            slider_fine.set_val(slider_fine.valmin)
        elif slider_fine.val > slider_fine.valmax:
            slider_fine.set_val(slider_fine.valmax)

        redraw()

    def timer_step():
        global playing

        if not playing:
            return

        new_t = slider_slice.val + dt

        if new_t > t.max():
            new_t = t.min()

        slider_slice.set_val(new_t)

    timer = fig.canvas.new_timer(interval=30)
    timer.add_callback(timer_step)
    timer.start()

    def toggle_play(event):
        global playing

        playing = not playing
        button_play.label.set_text("Pause" if playing else "Play")

    button_play.on_clicked(toggle_play)

    slider_slice.on_changed(redraw)
    slider_fine.on_changed(redraw)
    slider_width.on_changed(update_fine_range)

    redraw()
    plt.show()

visualize_slice()
# visualize_3d()