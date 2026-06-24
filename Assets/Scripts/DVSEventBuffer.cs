using System;
using System.Collections.Concurrent;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

public class DVSEventBuffer {
	private readonly ConcurrentQueue<Event> events = new ConcurrentQueue<Event>();

	private string outFilePath;

	private bool fileAvailable = true;
	private bool isOpen;

	private StreamWriter writer;
	private CancellationTokenSource flushCts;
	private Task flushTask;

	public void Setup(string cameraName) {
		outFilePath = Path.Combine(
			Application.dataPath,
			DVConfig.DataFolder,
			cameraName + ".txt");
	}

	public void Open() {
		if (isOpen)
			return;

		try {
			writer = new StreamWriter(outFilePath, append: false);
			writer.AutoFlush = false;

			flushCts = new CancellationTokenSource();
			flushTask = ConstantFlushLoop(flushCts.Token);

			isOpen = true;
			fileAvailable = true;
		} catch {
			Debug.LogError($"Error opening {outFilePath}. File output will be disabled.");
			fileAvailable = false;
			isOpen = false;
		}
	}

	// also force flushes everything 
	public async Task Close() {
		if (!isOpen)
			return;

		flushCts.Cancel();

		try {
			await flushTask;
		} catch (OperationCanceledException) {
		}

		await DrainOnce();
		await writer.FlushAsync();

		writer.Dispose();
		writer = null;

		flushCts.Dispose();
		flushCts = null;
		flushTask = null;

		isOpen = false;
	}

	public void NewEvent(int x, int y, ulong time, bool polarity) {
		events.Enqueue(new Event {
			x = x,
			y = y,
			t = time,
			p = polarity
		});
	}

	public async Task ForceFlush() {
		if (!fileAvailable || writer == null)
			return;

		await DrainOnce();
		await writer.FlushAsync();
	}

	private async Task ConstantFlushLoop(CancellationToken token) {
		while (!token.IsCancellationRequested) {
			await DrainOnce();

			if (writer != null)
				await writer.FlushAsync();

			await Task.Delay(DVConfig.EventFlushIntervalMs, token);
		}
	}

	private Task DrainOnce() {
		if (!fileAvailable || writer == null)
			return Task.CompletedTask;

		return Task.Run(() => {
			while (events.TryDequeue(out var e)) {
				writer.Write(e.x);
				writer.Write(", ");
				writer.Write(e.y);
				writer.Write(", ");
				writer.Write(e.t);
				writer.Write(", ");
				writer.WriteLine(e.p ? 1 : -1);
			}
		});
	}
}