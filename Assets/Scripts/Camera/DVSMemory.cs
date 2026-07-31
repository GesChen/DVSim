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

public class DVSMemory {
	// -- EVENTS --
	public readonly ConcurrentQueue<Event> eventQueue = new();

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

	List<(ulong t, Vector3 pos, Quaternion rot)> cameraRoute = new();

	public struct BBox {
		public string label;
		public uint ID;
		public ulong time;
		public S_Vector2 min;
		public S_Vector2 max;
		public float distance;
		public bool visible;
		public bool rendered;
	}
	List<BBox[]> bboxHistory = new();

	Dictionary<string, object> outputMetadata;

	static readonly string PostProcessPyFile = "Scripts\\postprocessoutput.py";

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
			camera.name + ".bin");

		Directory.CreateDirectory(Path.GetDirectoryName(eOutFilePath));

		isOpen = false;
	}

	public void Clear() {
		eventQueue.Clear();
		cameraRoute.Clear();
	}

	public void GenerateMeta() { // for a new permutation
		outputMetadata = new() {
			{ "permutation", DVManager.CurrentPermutation },
			{ "uniqueids", null },
			{ "simtime", -1f },

			{ "outfilepath", eOutFilePath },
			{ "absoluteassetpath", Application.dataPath },

			{ "camera", new Dictionary<string, object> {
				{ "position", (S_Vector3)camera.transform.position },
				{ "rotation", (S_Quaternion)camera.transform.rotation },

				{ "projection", camera.orthographic ? "orthographic" : "perspective" },
				{ "fov", camera.fieldOfView },
			}},

			{ "config", null}
		};

		outputMetadata["config"] = StaticClassToJObject(typeof(DVConfig));

		outputMetadata["uniqueids"] = DVManager.Instance.Objects.Select(o => o.ID.ToString()).ToArray();
	}

	public static JObject StaticClassToJObject(Type staticClass) {
		const BindingFlags flags =
		BindingFlags.Public |
		BindingFlags.Static |
		BindingFlags.FlattenHierarchy;

		static object ProcessUnserializables(object obj) {
			if (obj is Vector3Int v3i) return (S_Vector3)(Vector3)v3i;
			if (obj is Vector2Int v2i) return (S_Vector2)(Vector2)v2i;
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

		string dataPath = Path.Combine(
				Application.dataPath,
				DVConfig.outputFolder,
				DVConfig.permutationFolder,
				string.Join('_', permAtClose),
				name)
				.Replace('/', '\\');

		FinalizeWriteMetadata(dataPath); // do this immediately before awaiting, before things get deleted

		Log("Closing eventbuffer, awaiting flushtask");
		await CloseEventBuffer();

		try {
			if (DVConfig.recordCameraRoute)
				SaveCameraRoute(dataPath);

			if (DVConfig.recordBboxes)
				SaveBboxes(dataPath);

			Log("Post processing");
			TriggerPythonPostProcess(dataPath);
		} catch (Exception e) {
			LogError(e);
		}
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

	public void NewEvent(int x, int y, ulong time, bool polarity) {
		eventQueue.Enqueue(new Event {
			x = x,
			y = y,
			t = time,
			p = polarity
		});
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
				// int x      = 4 bytes
				// int y      = 4 bytes
				// ulong t    = 8 bytes
				// byte p     = 1 byte, 1 = ON, 0 = OFF
				// total      = 17 bytes/event

				eWriter.Write(e.x);
				eWriter.Write(e.y);
				eWriter.Write(e.t);
				eWriter.Write((byte)(e.p ? 1 : 0));

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

	void FinalizeWriteMetadata(string dataPath) {
		string jsonPath = Path.Combine(dataPath, DVConfig.metadataFileName);

		outputMetadata["simtime"] = DVManager.Instance.Stopwatch.Elapsed.TotalSeconds;

		string json = JsonConvert.SerializeObject(outputMetadata, Formatting.Indented);

		File.WriteAllText(jsonPath, json);

	}

	void TriggerPythonPostProcess(string dataPath) {
		string jsonPath = Path.Combine(dataPath, DVConfig.metadataFileName);

		var psi = new ProcessStartInfo {
			FileName = "cmd.exe",
			Arguments = $"/c \"py {PostProcessPyFile} \"{jsonPath}\"\"",
			UseShellExecute = true,
			CreateNoWindow = false,
			WorkingDirectory = Application.dataPath,
			WindowStyle = ProcessWindowStyle.Maximized
		};

		Log($"calling {psi.FileName} {psi.Arguments}");

		Process.Start(psi);
	}

	public void LogExtraData(ulong time) {
		if (DVConfig.recordCameraRoute)
			LogCameraRoute(time);

		if (DVConfig.recordBboxes)
			LogBboxes(time);
	}

	void LogCameraRoute(ulong time) {
		cameraRoute.Add((time, camera.transform.position, camera.transform.rotation));
	}

	void SaveCameraRoute(string dataPath) {
		Log("Saving camera route");
		string jsonPath = Path.Join(dataPath, DVConfig.camRouteFileName);

		List<object>[] convertedRoute =
			cameraRoute.Select(p => new List<object> {
				p.t,
				new float[] { p.pos.x, p.pos.y, p.pos.z },
				new float[] { p.rot.x, p.rot.y, p.rot.z, p.rot.w, } }).ToArray();

		string json = JsonConvert.SerializeObject(convertedRoute, Formatting.None);

		File.WriteAllText(jsonPath, json);
	}

	void LogBboxes(ulong time) {
		var bboxes = new BBox[DVManager.Instance.Objects.Count];
		for (int i = 0; i < DVManager.Instance.Objects.Count; i++) {
			DVObject obj = DVManager.Instance.Objects[i];

			BBox bbox = obj.GenerateBBoxExact(camera);
			bbox.label = obj.Label;
			bbox.ID = obj.ID;
			bbox.time = time;

			bboxes[i] = bbox;
		}

		bboxHistory.Add(bboxes);
	}

	void SaveBboxes(string dataPath) {
		Log("Saving bboxes");
		string jsonPath = Path.Join(dataPath, DVConfig.bboxFileName);

		string json = JsonConvert.SerializeObject(bboxHistory, Formatting.None);

		File.WriteAllText(jsonPath, json);
	}
}