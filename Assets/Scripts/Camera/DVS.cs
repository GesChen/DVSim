using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using Unity.Burst;
using Unity.Collections;
using Unity.Collections.LowLevel.Unsafe;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEditor;
using UnityEditorInternal;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;

public struct Event {
	public int x;
	public int y;
	public ulong t; // ns
	public bool p; // true = on, false = off
}


[DisallowMultipleComponent]
public class DVS : MonoBehaviour {
	public Camera camera;
	public DVSMemory memory;
	//public DVSFasterMemory fasterMemory;

	public bool Stereo;
	public float StereoSpacing = DVConfig.DefaultStereoSpacing;
	private DVS StereoLeft;
	private DVS StereoRight;

	DVMotion motionController;

	RenderTexture cameraTarget;
	RenderTexture sensorState;
	RenderTexture outputMap;
	RenderTexture debugOutput;

	private const string EventShaderAssetPath = "Assets/Scripts/Shaders/DVCalc.compute";
	ComputeShader EventShader;
	int eventKernel;

	private const string ImperfectionAssetPath = "Assets/Scripts/Shaders/Imperfection.compute";
	ComputeShader ImperfectionShader;
	RenderTexture ThreshNoiseRateRT;
	NativeArray<Vector4> ThreshNRData;

	// frame capture -------
	GraphicsBuffer frameCapOut;
	Texture2D frameCapColorTexture;
	Texture2D frameCapDataTexture;
	NativeArray<Vector4> fcColorPixels;
	NativeArray<Vector4> fcDataPixels;

	private const string FrameCapShaderAssetPath = "Assets/Scripts/Shaders/FrameCapture.compute";
	ComputeShader FrameCapShader;
	int frameCapKernel;

	// all shaders use the global texture, downscaling done in py post process
	Vector2Int globalShaderGroups;

	System.Random rng;

	bool hot;

	public void Init() {
		camera = GetComponent<Camera>();

		if (Stereo) {
			InitStereo();
			return;
		}

		cameraTarget = GenerateCameraRenTex(DVConfig.resolution);

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
		ThreshNRData = GenerateNativeArray();

		FrameCapShader = AssetDatabase.LoadAssetAtPath<ComputeShader>(FrameCapShaderAssetPath);
		frameCapKernel = FrameCapShader.FindKernel("Main");

		frameCapOut = new GraphicsBuffer(
			GraphicsBuffer.Target.Structured,
			DVConfig.resolution.x * DVConfig.resolution.y,
			24); // stride comes from float4 + float + float = 24 bytes

		if (DVConfig.useEXR) {
			frameCapColorTexture = GenerateTex2d();
			frameCapDataTexture = GenerateTex2d();
		}

		fcColorPixels = GenerateNativeArray();
		fcDataPixels = GenerateNativeArray();


		// wont change so you can precompute this
		globalShaderGroups = Vector2Int.CeilToInt((Vector2)DVConfig.resolution / 8f);

		memory = new();
		memory.Setup(camera);
		memory.Open();

		//fasterMemory = new();
		//fasterMemory.Setup(camera);
		//fasterMemory.Open();

		rng = new(DVConfig.Seed);

		SetupEventShader();

		if (TryGetComponent(out DVMotion mc)) {
			motionController = mc;
			mc.Initialize();
		}

		hot = true;
		Debug.Log($"DVS \"{camera.name}\" ready");
	}

	private static Texture2D GenerateTex2d() {
		return new Texture2D(DVConfig.resolution.x, DVConfig.resolution.y, TextureFormat.RGBAFloat, false);
	}

	private static NativeArray<Vector4> GenerateNativeArray() {
		return new NativeArray<Vector4>(DVConfig.resolution.x * DVConfig.resolution.y, Allocator.Persistent);
	}

	void InitStereo() {
		// disable this camera first in case it does any background processing
		camera.enabled = false;

		// generate stereo cameras in entirety
		StereoLeft = GenerateStereoSide(true);
		StereoRight = GenerateStereoSide(false);

		// invoke init
		StereoLeft.Init();
		StereoRight.Init();
	}

	DVS GenerateStereoSide(bool left) {
		GameObject obj = new(camera.name + (left ? "_left" : "_right"));
		Transform objt = obj.transform;
		objt.SetParent(transform);

		var cam = obj.AddComponent<Camera>();
		cam.CopyFrom(camera);

		objt.SetLocalPositionAndRotation((left ? -1 : 1) * StereoSpacing * Vector3.right, Quaternion.identity);

		DVS dvs = obj.AddComponent<DVS>();
		dvs.Stereo = false;

		return dvs;
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

		EventShader.SetBool("addPhotoAndShotNoise", DVConfig.photoNoise != DVConfig.PhotoNoiseBehaviour.None);
		float photoNoiseVolts = DVConfig.photoNoise switch {
			DVConfig.PhotoNoiseBehaviour.None => 0,
			DVConfig.PhotoNoiseBehaviour.v2e =>
				ComputePhotoreceptorNoiseVoltage(
					DVConfig.shotNoiseRateHz,
					DVConfig.photoNoiseCutoffHz, // f3db == cutoff hz
					DVConfig.simFPS,
					DVConfig.idealPosThresh,
					DVConfig.idealNegThresh,
					DVConfig.threshSigma
				),
			DVConfig.PhotoNoiseBehaviour.FixedVolts => DVConfig.fixedPhotoNoiseVolts,
			DVConfig.PhotoNoiseBehaviour.ApproximatedBA => ApproximateVoltage(DVConfig.simFPS, DVConfig.targetBA),
			_ => throw new IndexOutOfRangeException()
		};
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

				if (ThreshNRData.IsCreated)
					data.CopyTo(ThreshNRData);
			});
	}

	// v2e- emulator_utils.py
	static float ComputePhotoreceptorNoiseVoltage(
		float shotNoiseRateHz,
		float f3db,
		float sampleRateHz,
		float posThr,
		float negThr,
		float sigmaThr) {


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
			Debug.LogWarning(
				"THIS MAY CAUSE NO OUTPUT!!! >2.5 does not!!!");
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

	static float ApproximateVoltage(float fps, float targetBA) {
		float lba = Mathf.Log10(targetBA);
		float lfps = Mathf.Log10(fps);

		return 
			0.04725155f
			+ 0.00274859f * lba
			+ 0.00788103f * lfps
			+ 0.00955851f * lba * lfps
		;
	}

	// occurs after init, prepare for a new permutation
	public void Prepare(int[] perm) {
		if (Stereo) {
			StereoLeft.Prepare(perm);
			StereoRight.Prepare(perm);
			return;
		}

		ClearFrameFiles(perm);
		memory.Clear();
		memory.GenerateMeta();
	}

	public void Cleanup() {
		if (Stereo) {
			StereoLeft.Cleanup();
			StereoRight.Cleanup();
			return;
		}

		if (!hot) return;
		hot = false;

		if (camera != null)
			camera.targetTexture = null;

		Release(cameraTarget);
		Release(sensorState);
		Release(outputMap);
		Release(debugOutput);
		frameCapOut?.Release();
		if (DVConfig.useEXR) {
			Destroy(frameCapColorTexture);
			Destroy(frameCapDataTexture);
		}
		Release(ThreshNoiseRateRT);
		ThreshNRData.Dispose();

		_ = memory.Close();
		//fasterMemory.Close();
	}

	private void Release(RenderTexture rt) {
		if (rt == null)
			return;

		rt.Release();
		Destroy(rt);
	}

	public void Tick(ulong time) {
		if (Stereo) {
			StereoLeft.Tick(time);
			StereoRight.Tick(time);
			return;
		}

		if (motionController != null)
			motionController.UpdateMotion(time);

		//Debug.Log("tick");
		camera.Render();

		//if (DVManager.Frame % 10 == 0)
		//	RenderDoc.BeginCaptureRenderDoc(EditorWindow.focusedWindow);

		EventShader.SetTexture(eventKernel, "Camera", cameraTarget);
		EventShader.SetTexture(eventKernel, "State", sensorState);
		EventShader.SetTexture(eventKernel, "Output", outputMap);
		EventShader.SetTexture(eventKernel, "Debug", debugOutput);
		EventShader.SetBool("firstFrame", DVManager.Instance.Frame == 0);

		var iterSeed = rng.Next(int.MinValue, int.MaxValue);
		EventShader.SetInt("iterSeed", iterSeed);

		EventShader.Dispatch(eventKernel, globalShaderGroups.x, globalShaderGroups.y, 1);
		//if (DVManager.Frame == DVConfig.cameraWarmupTimeFrames)
		//if (DVManager.Frame % 10 == 0)
		//	RenderDoc.EndCaptureRenderDoc(EditorWindow.focusedWindow);

		ulong timeAtReq = time;
		ulong frameAtReq = DVManager.Instance.Frame;

		AsyncGPUReadback.Request(
			outputMap,
			0,
			TextureFormat.RFloat,
			req => Readback(req, timeAtReq, frameAtReq)
		);

		bool triggerOtherFPSEvent(float otherfps) =>
			Mathf.Floor(frameAtReq * otherfps / DVConfig.simFPS)
			!= Mathf.Floor((frameAtReq - 1) * otherfps / DVConfig.simFPS);

		if (DVConfig.doFrameCaptures && triggerOtherFPSEvent(DVConfig.frameCapFPS))
			TakeFrameCapture();

		if (triggerOtherFPSEvent(DVConfig.extraDataSampleRate))
			memory.LogExtraData(timeAtReq);
	}

	void Readback(AsyncGPUReadbackRequest request, ulong time, ulong frame) {
		if (frame < DVConfig.cameraWarmupTimeFrames) return;
		if (request.hasError) return;
		if (!DVManager.Instance.Playing) return;

		ulong dt = (ulong)math.round(DVConfig.timeScale / DVConfig.simFPS);

		NativeArray<float> outputData = request.GetData<float>();

		var eventQueue = new NativeQueue<Event>(Allocator.TempJob);
		var smallEventQueue = new NativeQueue<DVSFasterMemory.CompressedEvent>(Allocator.TempJob);

		new EventReadbackJob {
			OutputData = outputData,
			ThreshNoiseRateData = ThreshNRData,
			Events = eventQueue.AsParallelWriter(),
			CompressedEvents = smallEventQueue.AsParallelWriter(),

			Width = DVConfig.resolution.x,
			Height = DVConfig.resolution.y,

			Time = time,
			Dt = dt,

			EventCountScale = DVConfig.eventCountScale,
			InterpolateTime = DVConfig.interpolateTime
		}.Schedule(outputData.Length, 256).Complete();

		//Debug.Log($"generated {eventQueue.Count} event");

		while (eventQueue.TryDequeue(out Event e)) {
			memory.NewEvent(e.x, e.y, e.t, e.p);
		}

		/*while (smallEventQueue.TryDequeue(out DVSFasterMemory.CompressedEvent ce)) {
			fasterMemory.NewEvent(ce);
		}*/

		eventQueue.Dispose();
		smallEventQueue.Dispose();
		outputData.Dispose();
	}

	[StructLayout(LayoutKind.Sequential)]
	struct FCPixelData {
		public Vector4 color;
		public float depth;
		public float idBits;
	}

	void TakeFrameCapture() {
		Texture depthTex = Shader.GetGlobalTexture( "_ObjectLinearDepthTexture" );
		Texture idTex = Shader.GetGlobalTexture( "_ObjectIdTexture" );
		
		//RenderDoc.BeginCaptureRenderDoc(EditorWindow.focusedWindow);

		FrameCapShader.SetTexture(frameCapKernel, "Color", cameraTarget);
		FrameCapShader.SetTexture(frameCapKernel, "Depth", depthTex);
		FrameCapShader.SetTexture(frameCapKernel, "IDSegMap", idTex);
		FrameCapShader.SetBuffer(frameCapKernel, "Output", frameCapOut);

		FrameCapShader.Dispatch(frameCapKernel, globalShaderGroups.x, globalShaderGroups.y, 1);
		//RenderDoc.EndCaptureRenderDoc(EditorWindow.focusedWindow);

		string permutationAtCall = string.Join('_', DVManager.CurrentPermutation);
		int frameCapFrameAtCall = (int)(DVManager.Instance.Frame * DVConfig.frameCapFPS / DVConfig.simFPS);

		AsyncGPUReadback.Request(
			frameCapOut,
			req => FrameCapReadback(req, permutationAtCall, frameCapFrameAtCall)
		);
	}

	void FrameCapReadback(AsyncGPUReadbackRequest req, string permutation, int frame) {
		if (req.hasError) return;
		if (!DVManager.Instance.Playing) return;
		
		var source = req.GetData<FCPixelData>();

		new FrameCapUnpackJob {
			source = source,
			color = fcColorPixels,
			data = fcDataPixels
		}.Schedule(source.Length, 256).Complete();

		string frameFolder = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			DVConfig.permutationFolder,
			permutation,
			camera.name,
			DVConfig.frameCapSubFolder);

		Directory.CreateDirectory(frameFolder);

		string dataFolder = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			DVConfig.permutationFolder,
			permutation,
			camera.name,
			DVConfig.frameCapDataSubFolder);

		Directory.CreateDirectory(dataFolder);

		string ext = DVConfig.useEXR ? "exr" : "bytes";
		string colorFileName = Path.Combine(frameFolder, $"{frame.ToString("D" + DVConfig.frameNumDigits)}.{ext}");
		string dataFileName = Path.Combine(dataFolder, $"{frame.ToString("D" + DVConfig.frameNumDigits)}.{ext}");

		if (DVConfig.useEXR) {
			frameCapColorTexture.SetPixelData(fcColorPixels, 0);
			frameCapDataTexture.SetPixelData(fcDataPixels, 0);

			frameCapColorTexture.Apply(false, false);
			frameCapDataTexture.Apply(false, false);

			File.WriteAllBytes(
				colorFileName,
				frameCapColorTexture.EncodeToEXR());

			File.WriteAllBytes(
				dataFileName,
				frameCapDataTexture.EncodeToEXR(Texture2D.EXRFlags.OutputAsFloat));
		} else {
			WriteRaw(colorFileName, fcColorPixels);
			WriteRaw(dataFileName, fcDataPixels);
		}
	}

	static unsafe void WriteRaw<T>(
		string path,
		NativeArray<T> data)
		where T : unmanaged {

		int byteCount = data.Length * UnsafeUtility.SizeOf<T>();

		void* ptr = NativeArrayUnsafeUtility.GetUnsafeReadOnlyPtr(data);
		ReadOnlySpan<byte> bytes = new(ptr, byteCount);

		using FileStream stream = new(
			path,
			FileMode.Create,
			FileAccess.Write,
			FileShare.Read);

		stream.Write(bytes);
	}

	public void ClearFrameFiles(int[] permutation) {
		if (Stereo) {
			StereoLeft.ClearFrameFiles(permutation);
			StereoRight.ClearFrameFiles(permutation);
			return;
		}

		string permStr = string.Join('_', permutation);

		string colordir = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			DVConfig.permutationFolder,
			permStr,
			camera.name,
			DVConfig.frameCapSubFolder);

		if (Directory.Exists(colordir))
			Directory.Delete(colordir, true);
		Directory.CreateDirectory(colordir);

		string datadir = Path.Combine(
			Application.dataPath,
			DVConfig.outputFolder,
			DVConfig.permutationFolder,
			permStr,
			camera.name,
			DVConfig.frameCapDataSubFolder);

		if (Directory.Exists(datadir))
			Directory.Delete(datadir, true);
		Directory.CreateDirectory(datadir);
	}

	[BurstCompile]
	struct EventReadbackJob : IJobParallelFor {
		[ReadOnly] public NativeArray<float> OutputData;
		[ReadOnly] public NativeArray<Vector4> ThreshNoiseRateData;

		[WriteOnly] public NativeQueue<Event>.ParallelWriter Events;
		[WriteOnly] public NativeQueue<DVSFasterMemory.CompressedEvent>.ParallelWriter CompressedEvents;

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

			/*if (numEvents > 0)
				CompressedEvents.Enqueue(new() {
					position = index,
					time = Time,
					data = data
				});*/
		}
	}

	[BurstCompile]
	struct FrameCapUnpackJob : IJobParallelFor {
		[ReadOnly] public NativeArray<FCPixelData> source;
		[WriteOnly] public NativeArray<Vector4> color;
		[WriteOnly] public NativeArray<Vector4> data;

		public void Execute(int i) {
			FCPixelData p = source[i];

			color[i] = p.color;
			data[i] = new Vector4(
				p.depth,
				p.idBits,
				0,
				0);
		}
	}
}