from eventstream import EventStream

def background_activity(events, width, height):
    t = events.t
    duration = t.max() - t.min()

    if duration <= 0:
        return 0.0

    return len(t) / (width * height * duration)


events = EventStream.from_unity(r"E:\DVSim\Assets\.Output\Permutations\0_0_0_0_0_0\camera 2\events.npz")

ba = background_activity(events, width=1280, height=720)

print(f"{ba:.6f} events/pixel/s")