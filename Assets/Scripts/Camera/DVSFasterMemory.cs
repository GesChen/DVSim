using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

public class DVSFasterMemory {
	public struct CompressedEvent {
		public int position;
		public ulong time;
		public float data;
	}
	// -- EVENTS --
	public readonly ConcurrentQueue<CompressedEvent> eventQueue = new();

	string eOutFilePath;

	bool fileAvailable = true;
	bool isOpen;

	FileStream eStream;
	BinaryWriter eWriter;
	CancellationTokenSource flushCts;
	Task flushTask;

	// -- SCENE DATA --
	Camera camera;
	string name;

	void Log(object content) {
		UnityEngine.Debug.Log($"[{name}] {content}");
	}
	void LogError(object content) {
		UnityEngine.Debug.LogError($"[{name}] {content}");
	}

	public void Setup(Camera sourceCam) {
		camera = sourceCam;
		name = camera.name;

		eOutFilePath = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			camera.name + "_small.bin");

		Directory.CreateDirectory(Path.GetDirectoryName(eOutFilePath));

		isOpen = false;
	}

	public void Clear() {
		eventQueue.Clear();
	}

	public void Open() {
		if (isOpen)
			return;

		try {
			eStream = new FileStream(
				eOutFilePath,
				FileMode.Create,
				FileAccess.Write,
				FileShare.Read,
				bufferSize: 1024 * 1024);

			eWriter = new BinaryWriter(eStream);

			flushCts = new CancellationTokenSource();
			flushTask = ConstantFlushLoop(flushCts.Token);

			isOpen = true;
			fileAvailable = true;

			Log($"Successfully opened {eOutFilePath}");
		} catch {
			LogError($"Error opening {eOutFilePath}. File output will be disabled.");
			fileAvailable = false;
			isOpen = false;
		}
	}

	public async Task Close() {
		if (!isOpen)
			return;

		var permAtClose = DVManager.CurrentPermutation.ToArray();

		Log("Closing eventbuffer, awaiting flushtask");
		await CloseEventBuffer();
	}

	private async Task CloseEventBuffer() {
		flushCts.Cancel();

		try {
			await flushTask;
		} catch (OperationCanceledException) { // ignore the cancelled 
		} catch (Exception e) { // alert of other error
			LogError(e);
		}
		Log("Final drain and flush");

		await DrainOnce();
		eWriter.Flush();
		await eStream.FlushAsync();

		eWriter.Dispose();
		eWriter = null;
		eStream = null;

		flushCts.Dispose();
		flushCts = null;
		flushTask = null;

		isOpen = false;
	}

	public void NewEvent(CompressedEvent ce) {
		eventQueue.Enqueue(ce);
	}

	public async Task ForceFlush() {
		if (!fileAvailable || eWriter == null)
			return;

		await DrainOnce();
		eWriter.Flush();

		if (eStream != null)
			await eStream.FlushAsync();
	}

	private async Task ConstantFlushLoop(CancellationToken token) {
		while (!token.IsCancellationRequested) {
			await DrainOnce();

			if (eWriter != null)
				eWriter.Flush();

			if (eStream != null)
				await eStream.FlushAsync(token);

			await Task.Delay(DVConfig.eventFlushIntervalMs, token);
		}
	}

	private Task DrainOnce() {
		if (!fileAvailable || eWriter == null)
			return Task.CompletedTask;

		return Task.Run(() => {
			var sw = System.Diagnostics.Stopwatch.StartNew();

			long count = 0;
			long lastCount = 0;
			long lastMs = 0;

			while (eventQueue.TryDequeue(out var e)) {
				// Binary layout per event:
				// int pos = 4 bytes
				// float data = 4 bytes
				// total      = 8 bytes/event

				eWriter.Write(e.position);
				eWriter.Write(e.time);
				eWriter.Write(e.data);

				count++;

				long ms = sw.ElapsedMilliseconds;
				if (ms - lastMs >= 1000) {
					long delta = count - lastCount;
					double rate = delta * 1000.0 / (ms - lastMs);

					//Log($"Event write rate: {rate:N0}/s | total: {count:N0}");

					lastCount = count;
					lastMs = ms;
				}
			}

			double avgRate = count / Math.Max(sw.Elapsed.TotalSeconds, 1e-9);
			//Log($"Event write finished: {count:N0} events | avg: {avgRate:N0}/s");
		});
	}
}