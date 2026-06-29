import get_data
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import time

res = (1280, 720)

# (x, y, t, p) = get_data.load_umd_dataset(r'E:\DVSim\Python\data\from umd\events\sequence_haowen1_SIDE_DYNAMIC_DARK_bottle\proc\events')
(x, y, t, p) = get_data.load_unity_dataset(r'E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\Main Camera\events.npz')

# sort
(x, y, t, p) =  get_data.sortdata(x, y, t, p)

def visualize_3d():
    print('loading 3d graph...')
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')

    col = np.where(p == 1, 'red', 'blue')
    ax.scatter(x, t, y, marker='.', c=col, s=1)
    ax.set_xlabel('x')
    ax.set_ylabel('t')
    ax.set_zlabel('y')

    plt.show()

playing = False

def visualize_slice():
    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.35)

    # ax.set_xlim(x.min(), x.max())
    # ax.set_ylim(y.min(), y.max())

    ax.set_xlim(0, res[0])
    ax.set_ylim(0, res[1])

    timeslice = t[0]
    tslicewidth = 0.01

    ax_time = plt.axes([0.25, 0.20, 0.65, 0.03])
    slider_slice = Slider(ax_time, "Time Slice", t.min(), t.max(), valinit=timeslice)

    ax_width = plt.axes([0.25, 0.15, 0.65, 0.03])
    slider_width = Slider(ax_width, "Slice Width", 0.0, 0.1, valinit=tslicewidth)

    ax_button = plt.axes([0.45, 0.05, 0.15, 0.06])
    button_play = Button(ax_button, "Play")

    img = np.zeros((res[1], res[0], 3), dtype=np.uint8)

    im = ax.imshow(img, origin="lower", interpolation="nearest")
    ax.set_axis_off()

    dt = 0.038  # seconds advanced per timer tick

    def redraw(_=None):
        lo = np.searchsorted(t, slider_slice.val - slider_width.val / 2)
        hi = np.searchsorted(t, slider_slice.val + slider_width.val / 2)

        xs = x[lo:hi]
        ys = y[lo:hi]
        ps = p[lo:hi]
        
        pos = ps == 1
        neg = ~pos

        img.fill(0)
        img[ys[pos], xs[pos]] = [255, 0, 0]
        # img[ys[neg], xs[neg]] = [255, 0, 0]
        img[ys[neg], xs[neg]] = [0, 0, 255]

        im.set_data(img)
        fig.canvas.draw_idle()

    def timer_step():
        global playing

        if not playing:
            return

        new_t = slider_slice.val + dt

        if new_t > t.max():
            new_t = t.min()

        slider_slice.set_val(new_t)

    timer = fig.canvas.new_timer(interval=30)  # milliseconds
    timer.add_callback(timer_step)
    timer.start()

    def toggle_play(event):
        global playing

        playing = not playing
        button_play.label.set_text("Pause" if playing else "Play")

    button_play.on_clicked(toggle_play)

    slider_slice.on_changed(redraw)
    slider_width.on_changed(redraw)

    redraw()
    plt.show()

visualize_slice()
# visualize_3d()