import get_data
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import cv2

COLOR_MODE = "col"  # "col" or "bw"

USE_VIDEO_BACKGROUND = False
SOURCE_VIDEO_PATH = r"D:\Downloads\ytdlp\output.mp4"

# EVENT_RES = (1920, 1080)  # input event coordinate scale
EVENT_RES = (1280, 720)  # input event coordinate scale

# (x, y, t, p) = get_data.load_v2e_dataset(r"E:\DVSim\Python\v2e-master\v2ecore\output\output.npz")
# (x, y, t, p) = get_data.load_unity_dataset(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0\Main Camera\events.npz")
(x, y, t, p) = get_data.load_unity_dataset(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\camera 2\events.npz")

y = EVENT_RES[1] - y

(x, y, t, p) = get_data.sortdata(x, y, t, p)

if COLOR_MODE not in ("col", "bw"):
    raise ValueError('COLOR_MODE must be "col" or "bw"')


playing = False


def visualize_slice():
    global playing

    cap = None
    video_fps = 30.0
    video_frame_count = 0
    out_res = EVENT_RES

    if USE_VIDEO_BACKGROUND:
        cap = cv2.VideoCapture(SOURCE_VIDEO_PATH)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {SOURCE_VIDEO_PATH}")

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        video_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_res = (vid_w, vid_h)

        if video_fps <= 0:
            raise RuntimeError("Invalid video FPS.")

    sx = out_res[0] / EVENT_RES[0]
    sy = out_res[1] / EVENT_RES[1]

    def get_video_frame(center_t):
        frame_idx = int(round(center_t * video_fps))

        if video_frame_count > 0:
            frame_idx = np.clip(frame_idx, 0, video_frame_count - 1)

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

        ok, frame = cap.read()
        if not ok:
            return np.zeros((out_res[1], out_res[0], 3), dtype=np.uint8)

        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    fig, ax = plt.subplots()
    plt.subplots_adjust(bottom=0.42)

    ax.set_xlim(0, out_res[0])
    ax.set_ylim(out_res[1], 0)

    timeslice = float(t[0])
    tslicewidth = 0.01

    ax_time = plt.axes([0.25, 0.25, 0.65, 0.03])
    slider_slice = Slider(ax_time, "Time Slice", t.min(), t.max(), valinit=timeslice)

    ax_fine = plt.axes([0.25, 0.20, 0.65, 0.03])
    slider_fine = Slider(ax_fine, "Fine Offset", -tslicewidth / 2, tslicewidth / 2, valinit=0.0)

    ax_width = plt.axes([0.25, 0.15, 0.65, 0.03])
    slider_width = Slider(ax_width, "Slice Width", 0.0, 0.10, valinit=tslicewidth)

    ax_button = plt.axes([0.45, 0.05, 0.15, 0.06])
    button_play = Button(ax_button, "Play")

    count_text = fig.text(
        0.5,
        0.34,
        "",
        ha="center",
        va="center"
    )

    img = np.zeros((out_res[1], out_res[0], 3), dtype=np.uint8)
    im = ax.imshow(img, interpolation="nearest")
    ax.set_axis_off()

    dt = 1.0 / video_fps

    def redraw(_=None):
        center_t = slider_slice.val + slider_fine.val
        width = slider_width.val

        lo = np.searchsorted(t, center_t - width / 2)
        hi = np.searchsorted(t, center_t + width / 2)

        event_count = hi - lo
        count_text.set_text(f"Events in slice: {event_count:,}")

        xs = (x[lo:hi] * sx).astype(np.int64)
        ys = (y[lo:hi] * sy).astype(np.int64)
        ps = p[lo:hi]

        valid = (xs >= 0) & (xs < out_res[0]) & (ys >= 0) & (ys < out_res[1])
        xs = xs[valid]
        ys = ys[valid]
        ps = ps[valid]

        if USE_VIDEO_BACKGROUND:
            img = get_video_frame(center_t)
        else:
            img = np.zeros((out_res[1], out_res[0], 3), dtype=np.uint8)
            if COLOR_MODE != "col":
                img.fill(127)

        pos = ps == 1
        neg = ~pos

        if COLOR_MODE == "col":
            img[ys[pos], xs[pos]] = [255, 0, 0]
            img[ys[neg], xs[neg]] = [0, 0, 255]
        else:
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

        if USE_VIDEO_BACKGROUND:
            max_video_t = (video_frame_count - 1) / video_fps
            max_t = min(float(t.max()), max_video_t)
        else:
            max_t = float(t.max())

        if new_t > max_t:
            new_t = float(t.min())

        slider_slice.set_val(new_t)

    timer = fig.canvas.new_timer(interval=int(1000 / video_fps))
    timer.add_callback(timer_step)
    timer.start()

    def toggle_play(event):
        global playing
        playing = not playing
        button_play.label.set_text("Pause" if playing else "Play")

    def on_close(_):
        if cap is not None:
            cap.release()

    fig.canvas.mpl_connect("close_event", on_close)

    button_play.on_clicked(toggle_play)
    slider_slice.on_changed(redraw)
    slider_fine.on_changed(redraw)
    slider_width.on_changed(update_fine_range)

    redraw()
    plt.show()


visualize_slice()