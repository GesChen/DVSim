using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Linq;

public class DVSEventBuffer {
	public List<Event> Events;

	string outFilePath;

	public void Setup(string cameraName) {
		outFilePath = Path.Combine(Application.dataPath, DVConfig.DataFolder, cameraName + ".txt");

		File.WriteAllText(outFilePath, string.Empty);
	}

	public DVSEventBuffer() {
		Events = new List<Event>(DVConfig.EventBufferCap);
	}

	public void NewEvent(int x, int y, ulong time, bool polarity) {
		Events.Add(new() {
			x = x,
			y = y,
			t = time,
			p = polarity
		});

		if (Events.Count > DVConfig.EventBufferFlush)
			_ = Flush();
	}

	public async Task Flush() {
		string content = EventsToString();
		Events.Clear();

		await File.AppendAllTextAsync(outFilePath, content + "\n");
	}

	string EventsToString() =>
		string.Join('\n', Events.Select(e => EventToString(e)));

	string EventToString(Event e) =>
		$"{e.x}, {e.y}, {e.t}, {(e.p ? "1" : "-1")}";
}