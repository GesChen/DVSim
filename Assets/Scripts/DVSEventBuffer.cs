using UnityEngine;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Linq;

public class DVSEventBuffer {
	public List<Event> Events;

	string outFilePath;

	bool fileAvailable = true;
	public void Setup(string cameraName) {
		outFilePath = Path.Combine(Application.dataPath, DVConfig.DataFolder, cameraName + ".txt");

		try {
			File.WriteAllText(outFilePath, string.Empty);
		} catch {
			Debug.LogError($"Error writing to {outFilePath}. File output will be disabled for this camera.");
			fileAvailable = false;
		}
	}

	public DVSEventBuffer() {
		Events = new List<Event>(DVConfig.EventBufferCap);
	}

	private bool flushing;

	public void NewEvent(int x, int y, ulong time, bool polarity) {
		Events.Add(new Event {
			x = x,
			y = y,
			t = time,
			p = polarity
		});

		if (!flushing && Events.Count > DVConfig.EventBufferFlush)
			_ = FlushLoop();
	}

	public void ForceFlush(bool bypass = false) {
		if (flushing && !bypass) {
			Debug.LogWarning("Can't force flush. Buffer is already flushing.");
			return;
		}

		Debug.Log($"Force flushing {Events.Count} events");
		_ = FlushLoop();
	}

	private async Task FlushLoop() {
		if (!fileAvailable) return;

		flushing = true;

		while (Events.Count > 0) {
			var snapshot = Events.ToArray();
			Events.Clear();

			string content = await Task.Run(() =>
			{
				var sb = new System.Text.StringBuilder(snapshot.Length * 32);

				foreach (var e in snapshot)
			{
					sb.Append(e.x).Append(", ")
				  .Append(e.y).Append(", ")
				  .Append(e.t).Append(", ")
				  .Append(e.p ? "1" : "-1")
				  .Append('\n');
				}

				return sb.ToString();
			});

			await File.AppendAllTextAsync(outFilePath, content);
		}

		flushing = false;
	}
}