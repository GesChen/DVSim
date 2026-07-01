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
using UnityEngine;

public class DVSEventBuffer {
	public readonly ConcurrentQueue<Event> queue = new();

	string outFilePath;

	bool fileAvailable = true;
	bool isOpen;

	FileStream stream;
	BinaryWriter writer;
	CancellationTokenSource flushCts;
	Task flushTask;

	Camera camera;

	Dictionary<string, object> outputMetadata;

	static readonly string PostProcessPyFile = "Scripts/postprocessoutput_log.py";

	public void Setup(Camera sourceCam) {
		camera = sourceCam;

		outFilePath = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			camera.name + ".bin");

		Directory.CreateDirectory(Path.GetDirectoryName(outFilePath));

		isOpen = false;

	}

	void GenerateMeta() {
		outputMetadata = new() {
			{ "outfilepath", outFilePath },
			{ "permutation", DVManager.CurrentPermutation },

			{ "config", null},

			{ "camera", new Dictionary<string, object> {
				{ "position", (S_Vector3)camera.transform.position },
				{ "rotation", (S_Quaternion)camera.transform.rotation },

				{ "projection", camera.orthographic ? "orthographic" : "perspective" },
				{ "fov", camera.fieldOfView },

				{ "resolution", new[] { camera.pixelWidth, camera.pixelHeight } },
			}}
		};

		outputMetadata["config"] = StaticClassToJObject(typeof(DVConfig));
	}

	public static JObject StaticClassToJObject(Type staticClass) {
		const BindingFlags flags =
		BindingFlags.Public |
		BindingFlags.Static |
		BindingFlags.FlattenHierarchy;

		static object ProcessUnserializables(object obj) {
			if (obj is Vector3Int v3i) return (S_Vector3)(Vector3)v3i;
			return obj;
		}

		var obj = new JObject();

		foreach (var field in staticClass.GetFields(flags)) {
			obj[field.Name] = JToken.FromObject(field.GetValue(null));
		}

		foreach (var prop in staticClass.GetProperties(flags)) {
			if (!prop.CanRead) continue;
			if (prop.GetIndexParameters().Length > 0) continue;

			obj[prop.Name] = JToken.FromObject(ProcessUnserializables(prop.GetValue(null)));
		}

		return obj;
	}

	public void Open() {
		if (isOpen)
			return;

		try {
			stream = new FileStream(
				outFilePath,
				FileMode.Create,
				FileAccess.Write,
				FileShare.Read,
				bufferSize: 1024 * 1024);

			writer = new BinaryWriter(stream);

			flushCts = new CancellationTokenSource();
			flushTask = ConstantFlushLoop(flushCts.Token);

			isOpen = true;
			fileAvailable = true;
		} catch {
			UnityEngine.Debug.LogError($"Error opening {outFilePath}. File output will be disabled.");
			fileAvailable = false;
			isOpen = false;
		}
	}

	public async Task Close() {
		if (!isOpen)
			return;

		var permAtClose = DVManager.CurrentPermutation.ToArray();

		UnityEngine.Debug.Log("Closing eventbuffer, awaiting flushtask");

		flushCts.Cancel();

		try {
			await flushTask;
		} catch (OperationCanceledException) {
		}

		UnityEngine.Debug.Log("Final drain and flush");

		await DrainOnce();
		writer.Flush();
		await stream.FlushAsync();

		writer.Dispose();
		writer = null;
		stream = null;

		flushCts.Dispose();
		flushCts = null;
		flushTask = null;

		isOpen = false;

		UnityEngine.Debug.Log("Eventbuffer finished closing. Post processing");

		try {
			_ = TriggerPythonPostProcessAsync(permAtClose);
		} catch (Exception e) {
			UnityEngine.Debug.LogError(e);
		}
	}

	public void NewEvent(int x, int y, ulong time, bool polarity) {
		queue.Enqueue(new Event {
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
		writer.Flush();

		if (stream != null)
			await stream.FlushAsync();
	}

	private async Task ConstantFlushLoop(CancellationToken token) {
		while (!token.IsCancellationRequested) {
			await DrainOnce();

			if (writer != null)
				writer.Flush();

			if (stream != null)
				await stream.FlushAsync(token);

			await Task.Delay(DVConfig.eventFlushIntervalMs, token);
		}
	}

	private Task DrainOnce() {
		if (!fileAvailable || writer == null)
			return Task.CompletedTask;

		return Task.Run(() => {
			var sw = System.Diagnostics.Stopwatch.StartNew();

			long count = 0;
			long lastCount = 0;
			long lastMs = 0;

			while (queue.TryDequeue(out var e)) {
				// Binary layout per event:
				// int x      = 4 bytes
				// int y      = 4 bytes
				// ulong t    = 8 bytes
				// byte p     = 1 byte, 1 = ON, 0 = OFF
				// total      = 17 bytes/event

				writer.Write(e.x);
				writer.Write(e.y);
				writer.Write(e.t);
				writer.Write((byte)(e.p ? 1 : 0));

				count++;

				long ms = sw.ElapsedMilliseconds;
				if (ms - lastMs >= 1000) {
					long delta = count - lastCount;
					double rate = delta * 1000.0 / (ms - lastMs);

					UnityEngine.Debug.Log($"Event write rate: {rate:N0}/s | total: {count:N0}");

					lastCount = count;
					lastMs = ms;
				}
			}

			double avgRate = count / Math.Max(sw.Elapsed.TotalSeconds, 1e-9);
			UnityEngine.Debug.Log($"Event write finished: {count:N0} events | avg: {avgRate:N0}/s");
		});
	}

	async Task TriggerPythonPostProcessAsync(int[] permutationAtClose) {
		string script = Path.Combine(Application.dataPath, PostProcessPyFile)
		.Replace('/', '\\');

		GenerateMeta();

		string jsonPath = Path.Combine(
		Application.dataPath,
		DVConfig.outputFolder,
		DVConfig.permutationFolder,
		string.Join('_', permutationAtClose),
		camera.name,
		"meta.json");

		string json = JsonConvert.SerializeObject(outputMetadata, Formatting.Indented);

		await File.WriteAllTextAsync(jsonPath, json);

		using var p = new Process();

		p.StartInfo.FileName = "py";
		p.StartInfo.Arguments = $"\"{script}\" \"{jsonPath}\"";
		p.StartInfo.UseShellExecute = false;
		p.StartInfo.RedirectStandardOutput = true;
		p.StartInfo.RedirectStandardError = true;
		p.StartInfo.CreateNoWindow = true;

		UnityEngine.Debug.Log($"calling py {p.StartInfo.Arguments}");

		p.Start();

		Task<string> stdoutTask = p.StandardOutput.ReadToEndAsync();
		Task<string> stderrTask = p.StandardError.ReadToEndAsync();

#if NET5_0_OR_GREATER
    await p.WaitForExitAsync();
#else
		await Task.Run(() => p.WaitForExit());
#endif

		string stdout = await stdoutTask;
		string stderr = await stderrTask;

		if (!string.IsNullOrWhiteSpace(stdout))
			UnityEngine.Debug.Log(stdout);

		if (!string.IsNullOrWhiteSpace(stderr))
			UnityEngine.Debug.LogError(stderr);

		UnityEngine.Debug.Log($"done, exit code {p.ExitCode}");
	}
}