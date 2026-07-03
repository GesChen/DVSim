using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEditor;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEditorInternal;

public struct Event {
	public int x;
	public int y;
	public ulong t; // ns
	public bool p; // true = on, false = off
}


[DisallowMultipleComponent]
public class DVS : MonoBehaviour {
	public Camera camera;
	public DVSEventBuffer events;

	RenderTexture cameraTarget;
	RenderTexture sensorState;
	RenderTexture outputMap;
	RenderTexture debugOutput;

	private const string EventShaderAssetPath = "Assets/Scripts/DVCalc.compute";
	ComputeShader EventShader;
	int eventKernel;

	private const string ImperfectionAssetPath = "Assets/Scripts/Imperfection.compute";
	ComputeShader ImperfectionShader;
	RenderTexture ThreshNoiseRateRT;
	NativeArray<Vector4> ThreshNRData;

	// frame capture -------
	RenderTexture frameCapOut;
	Texture2D frameCapTexture;

	private const string FrameCapShaderAssetPath = "Assets/Scripts/FrameCapture.compute";
	ComputeShader FrameCapShader;
	int frameCapKernel;

	// all shaders use the global texture, downscaling done in py post process
	Vector2Int globalShaderGroups;

	System.Random rng;

	public void Init() {
		cameraTarget = GenerateCameraRenTex(DVConfig.resolution);

		camera = GetComponent<Camera>();
		camera.allowHDR = true;
		camera.targetTexture = cameraTarget;
		camera.depthTextureMode |= DepthTextureMode.Depth;

		sensorState = GenerateNonDepthRenTex(RenderTextureFormat.ARGBFloat);
		outputMap = GenerateNonDepthRenTex(RenderTextureFormat.RFloat);
		debugOutput = GenerateNonDepthRenTex(RenderTextureFormat.ARGBFloat);

		EventShader = AssetDatabase.LoadAssetAtPath<ComputeShader>(EventShaderAssetPath);
		eventKernel = EventShader.FindKernel("Main");

		ImperfectionShader = AssetDatabase.LoadAssetAtPath<ComputeShader>(ImperfectionAssetPath);
		ThreshNoiseRateRT = GenerateNonDepthRenTex(RenderTextureFormat.ARGBFloat);
		ThreshNRData = new NativeArray<Vector4>(DVConfig.resolution.x * DVConfig.resolution.y, Allocator.Persistent);

		frameCapOut = GenerateNonDepthRenTex(RenderTextureFormat.ARGBFloat);
		frameCapTexture = new Texture2D(DVConfig.resolution.x, DVConfig.resolution.y, TextureFormat.RGBAFloat, false);

		FrameCapShader = AssetDatabase.LoadAssetAtPath<ComputeShader>(FrameCapShaderAssetPath);
		frameCapKernel = FrameCapShader.FindKernel("Main");

		// wont change so you can precompute this
		globalShaderGroups = Vector2Int.CeilToInt((Vector2)DVConfig.resolution / 8f);

		events = new();
		events.Setup(camera);
		events.Open();

		rng = new(DVConfig.Seed);

		SetupEventShader();
	}

	RenderTexture GenerateCameraRenTex(Vector2Int res) {
		var tex = new RenderTexture(
			new RenderTextureDescriptor(res.x, res.y)
			{
				graphicsFormat = GraphicsFormat.R16G16B16A16_SFloat,
				depthBufferBits = 24,
				msaaSamples = 1,          // no MSAA
				sRGB = true,
				enableRandomWrite = false  // only if used by compute shaders
			}
		);

		tex.Create();
		return tex;
	}

	RenderTexture GenerateNonDepthRenTex(RenderTextureFormat format) {
		RenderTexture tex = new(
			DVConfig.resolution.x,
			DVConfig.resolution.y,
			0,
			format
		);
		tex.enableRandomWrite = true;
		tex.Create();

		return tex;
	}

	void SetupEventShader() {
		EventShader.SetFloat("runSeed", unchecked((int)DVConfig.Seed));
		EventShader.SetFloat("EventCountScale", DVConfig.eventCountScale);
		EventShader.SetFloat("dtSecs", 1 / DVConfig.simFPS);
		EventShader.SetFloat("tauOn", DVConfig.tauOn);
		EventShader.SetFloat("tauOff", DVConfig.tauOff);
		EventShader.SetFloat("leakRateHz", DVConfig.leakRateHz);
		EventShader.SetFloat("leakJitterFraction", DVConfig.leakJitterFraction);

		EventShader.SetBool("addPhotoAndShotNoise", DVConfig.doPhotoreceptorNoise);
		float photoNoiseVolts;
		if (DVConfig.doPhotoreceptorNoise)
			photoNoiseVolts = ComputePhotoreceptorNoiseVoltage(
				DVConfig.shotNoiseRateHz,
				DVConfig.photoNoiseCutoffHz, // f3db == cutoff hz
				DVConfig.simFPS,
				DVConfig.idealPosThresh,
				DVConfig.idealNegThresh,
				DVConfig.threshSigma
			);
		else
			photoNoiseVolts = 0;
		EventShader.SetFloat("photoNoiseVoltage", photoNoiseVolts);
		EventShader.SetFloat("photoNoiseCutoffHz", DVConfig.photoNoiseCutoffHz);

		// precompute simulated imperfections
		// this generates technically two textures,
		// one variable threshold texture r g
		// one leakrate texture b

		int imperfectInitKernel = ImperfectionShader.FindKernel("VariableThreshAndLeak");
		ImperfectionShader.SetInt("runSeed", DVConfig.Seed);
		ImperfectionShader.SetFloat("threshSigma", DVConfig.threshSigma);
		ImperfectionShader.SetFloat("idealPosThresh", DVConfig.idealPosThresh);
		ImperfectionShader.SetFloat("idealNegThresh", DVConfig.idealNegThresh);
		ImperfectionShader.SetBool ("doLeaking", DVConfig.leakRateHz > 0);
		ImperfectionShader.SetFloat("noiseRateCovDecades", DVConfig.noiseRateCovDecades);
		ImperfectionShader.SetTexture(imperfectInitKernel, "VaryThreshsAndNoiseRate", ThreshNoiseRateRT);
		
		ImperfectionShader.Dispatch(imperfectInitKernel, globalShaderGroups.x, globalShaderGroups.y, 1);

		// give this imperfection data to the event shader- set once, it doesn't change later
		EventShader.SetTexture(imperfectInitKernel, "ThreshAndNoiseRate", ThreshNoiseRateRT);

		// copy the raw data to a nativearray for the burst job to use later 
		AsyncGPUReadback.Request(ThreshNoiseRateRT, 0, TextureFormat.RGBAFloat,
			req => {
				if (req.hasError) return;
				
				var data = req.GetData<Vector4>();

				data.CopyTo(ThreshNRData);
			});
	}

	// v2e- emulator_utils.py
	public static float ComputePhotoreceptorNoiseVoltage(
		float shotNoiseRateHz,
		float f3db,
		float sampleRateHz,
		float posThr,
		float negThr,
		float sigmaThr) {

		float ratePerBw = (shotNoiseRateHz / f3db) * 0.5f;

		if (ratePerBw > 0.5f)
			Debug.LogWarning($"shot noise rate per Hz bandwidth is large: rate={shotNoiseRateHz}, f3db={f3db}");

		float x = Mathf.Log10(ratePerBw);

		if (x < -5f)
			Debug.LogWarning($"desired noise rate {shotNoiseRateHz} Hz is too low for accurate threshold estimation");
		else if (x > 0f)
			Debug.LogWarning($"desired noise rate {shotNoiseRateHz} Hz is too large for accurate threshold estimation");

		const int N = 300;
		float vnSum = 0f;

		for (int i = 0; i < N; i++) {
			float pos = posThr + sigmaThr * RandNormal();
			float neg = negThr + sigmaThr * RandNormal();
			float thr = Mathf.Min(pos, neg);

			vnSum += ComputeVnFromLogRatePerHz(thr, x);
		}

		float vn = vnSum / N;

		float tau = 1f / (f3db * 2f * Mathf.PI);
		float dt = 1f / sampleRateHz;
		float eps = dt / tau;

		if (eps > 0.1f) {
			Debug.LogWarning(
				$"eps={eps:F3} for IIR lowpass is > 0.1. " +
				$"Increase sample rate or decrease cutoff_hz. dt={dt:F6}s, cutoff={f3db:F3}Hz");
		}

		int len = Mathf.Max(2, Mathf.CeilToInt((1000f * tau) / dt));

		float[] rin = new float[len];
		float[] rout = new float[len];

		for (int i = 0; i < len; i++)
			rin[i] = vn * RandNormal();

		float rmsIn = StdDev(rin);

		rout[0] = 0f;
		for (int i = 1; i < len; i++)
			rout[i] = rout[i - 1] * (1f - eps) + rin[i] * eps;

		float rmsOut = StdDev(rout);
		float scale = rmsIn / rmsOut;
		float vnScaled = scale * vn;

		return vnScaled;
	}

	static float ComputeVnFromLogRatePerHz(float thr, float x) {
		float x2 = x * x;
		float x3 = x2 * x;

		float y =
			- 0.0026f * x3
			- 0.036f * x2
			- 0.1949f * x
			+ 0.321f;

		float thrPerVn = Mathf.Pow(10f, y);
		return thr / thrPerVn;
	}

	// Box-Muller normal RNG, mean 0, std 1.
	static float RandNormal() {
		float u1 = Mathf.Max(UnityEngine.Random.value, 1e-7f);
		float u2 = UnityEngine.Random.value;

		return Mathf.Sqrt(-2f * Mathf.Log(u1)) *
			   Mathf.Cos(2f * Mathf.PI * u2);
	}

	static float StdDev(float[] values) {
		float mean = 0f;
		for (int i = 0; i < values.Length; i++)
			mean += values[i];

		mean /= values.Length;

		float var = 0f;
		for (int i = 0; i < values.Length; i++) {
			float d = values[i] - mean;
			var += d * d;
		}

		return Mathf.Sqrt(var / values.Length);
	}

	public void Cleanup() {
		if (camera != null)
			camera.targetTexture = null;

		Release(cameraTarget);
		Release(sensorState);
		Release(outputMap);
		Release(debugOutput);
		Release(frameCapOut);
		Destroy(frameCapTexture);
		Release(ThreshNoiseRateRT);
		ThreshNRData.Dispose();

		_ = events.Close();
	}

	private void Release(RenderTexture rt) {
		if (rt == null)
			return;

		rt.Release();
		Destroy(rt);
	}

	public void Tick() {
		//Debug.Log("tick");
		camera.Render();

		//if (DVManager.Frame % 10 == 0)
		//	RenderDoc.BeginCaptureRenderDoc(EditorWindow.focusedWindow);

		EventShader.SetTexture(eventKernel, "Camera", cameraTarget);
		EventShader.SetTexture(eventKernel, "State", sensorState);
		EventShader.SetTexture(eventKernel, "Output", outputMap);
		EventShader.SetTexture(eventKernel, "Debug", debugOutput);
		EventShader.SetBool("firstFrame", DVManager.Frame == 0);

		var iterSeed = rng.Next(int.MinValue, int.MaxValue);
		EventShader.SetInt("iterSeed", iterSeed);

		EventShader.Dispatch(eventKernel, globalShaderGroups.x, globalShaderGroups.y, 1);
		//if (DVManager.Frame == DVConfig.cameraWarmupTimeFrames)
		//if (DVManager.Frame % 10 == 0)
		//	RenderDoc.EndCaptureRenderDoc(EditorWindow.focusedWindow);

		ulong timeAtReq = DVManager.Time;
		ulong frameAtReq = DVManager.Frame;

		AsyncGPUReadback.Request(
			outputMap,
			0,
			TextureFormat.RFloat,
			req => Readback(req, timeAtReq, frameAtReq)
		);

		if (DVConfig.doFrameCaptures && (DVManager.Frame % (DVConfig.simFPS / DVConfig.frameCapFPS)) < 1f)
			TakeFrameCapture();
	}

	void Readback(AsyncGPUReadbackRequest request, ulong time, ulong frame) {
		if (frame < DVConfig.cameraWarmupTimeFrames) return;
		if (request.hasError) return;
		if (!DVManager.Playing) return;

		ulong dt = (ulong)math.round(DVConfig.timeScale / DVConfig.simFPS);

		NativeArray<float> outputData = request.GetData<float>();

		var eventQueue = new NativeQueue<Event>(Allocator.TempJob);

		var job = new ReadbackJob {
			OutputData = outputData,
			ThreshNoiseRateData = ThreshNRData,
			Events = eventQueue.AsParallelWriter(),

			Width = DVConfig.resolution.x,
			Height = DVConfig.resolution.y,

			Time = time,
			Dt = dt,

			EventCountScale = DVConfig.eventCountScale,
			InterpolateTime = DVConfig.interpolateTime
		};

		JobHandle handle = job.Schedule(outputData.Length, 128);
		handle.Complete();

		while (eventQueue.TryDequeue(out Event e)) {
			events.NewEvent(e.x, e.y, e.t, e.p);
		}

		eventQueue.Dispose();
		outputData.Dispose();
	}

	void TakeFrameCapture() {
		FrameCapShader.SetTexture(frameCapKernel, "Color", cameraTarget);
		Texture depth = Shader.GetGlobalTexture("_CameraDepthTexture"); // TODO: fix this.. 
		// weird unity 6 new rendering system makes this no longer work. 
		FrameCapShader.SetTexture(frameCapKernel, "Depth", depth);
		FrameCapShader.SetTexture(frameCapKernel, "Result", frameCapOut);

		FrameCapShader.Dispatch(frameCapKernel, globalShaderGroups.x, globalShaderGroups.y, 1);

		string permutationAtCall = string.Join('_', DVManager.CurrentPermutation);
		int frameCapFrameAtCall = (int)(DVManager.Frame * DVConfig.frameCapFPS / DVConfig.simFPS);

		AsyncGPUReadback.Request(
			frameCapOut,
			0,
			TextureFormat.RGBAFloat,
			req => FrameCapReadback(req, permutationAtCall, frameCapFrameAtCall)
		);
	}

	void FrameCapReadback(AsyncGPUReadbackRequest req, string permutation, int frame) {
		if (req.hasError)
			return;
		if (frameCapTexture == null) return; 

		var data = req.GetData<Vector4>(); // or Color32 / float / half-compatible struct

		frameCapTexture.SetPixelData(data, 0);
		frameCapTexture.Apply(false);

		byte[] bytes = frameCapTexture.EncodeToEXR(); // HDR-safe

		string location = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			DVConfig.permutationFolder,
			permutation,
			camera.name,
			DVConfig.frameCapSubFolder);

		Directory.CreateDirectory(location);

		string fullPath = Path.Combine(location, $"{frame.ToString("D" + DVConfig.frameNumPadDigits)}.exr");

		File.WriteAllBytes(fullPath, bytes);

	}

	public void ClearFrameCaptures(int[] permutation) {
		string permStr = string.Join('_', permutation);

		string location = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			DVConfig.permutationFolder,
			permStr,
			camera.name,
			DVConfig.frameCapSubFolder);

		if (Directory.Exists(location))
			Directory.Delete(location, true);
		Directory.CreateDirectory(location);
	}
}

[BurstCompile]
public struct ReadbackJob : IJobParallelFor {
	[ReadOnly] public NativeArray<float> OutputData;
	[ReadOnly] public NativeArray<Vector4> ThreshNoiseRateData;

	public NativeQueue<Event>.ParallelWriter Events;

	public int Width;
	public int Height;

	public ulong Time;
	public ulong Dt;

	public int EventCountScale;
	public bool InterpolateTime;

	public void Execute(int index) {
		float data = OutputData[index];

		if (data == 0) return;

		int numEvents = (int)math.floor(math.abs(data) / EventCountScale);

		int x = index % Width;
		int y = index / Width;

		bool on = data > 0f;
		int polarity = on ? 1 : -1;
		float diff = polarity * (math.abs(data) - numEvents * EventCountScale);

		Vector4 threshData = ThreshNoiseRateData[index];
		float ContrastThreshold = on ? threshData.x : threshData.y;

		ulong lastTime = Time;
		ulong t = Time;
		for (int n = 0; n < numEvents; n++) {

			if (InterpolateTime) {
				float crossing = polarity * (n + 1) * ContrastThreshold;
				float alpha = crossing / diff;
				t = Time + (ulong)math.round(alpha * Dt);

				if (t < lastTime + DVConfig.refractoryPeriod) continue;
			}

			lastTime = t;

			Events.Enqueue(new Event {
				x = x,
				y = y,
				t = t,
				p = on
			});
		}
	}
}