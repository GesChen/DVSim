using System;
using System.Linq;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using Unity.Mathematics;
using UnityEditor;
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
	public DVSEventBuffer events;

	RenderTexture cameraTarget;
	RenderTexture sensorState;
	RenderTexture outputMap;

	private const string EventShaderAssetPath = "Assets/Scripts/DVCalc.compute";
	ComputeShader EventShader;
	int eventKernel;

	// all shaders use the global texture, downscaling done in py post process
	Vector2Int globalShaderGroups;

	// frame capture -------
	RenderTexture frameCapOut;
	Texture2D frameCapTexture;

	private const string FrameCapShaderAssetPath = "Assets/Scripts/FrameCapture.compute";
	ComputeShader FrameCapShader;
	int frameCapKernel;

	public void Init() {
		cameraTarget = GenerateCameraRenTex(DVConfig.Resolution);

		camera = GetComponent<Camera>();
		camera.allowHDR = true;
		camera.targetTexture = cameraTarget;
		camera.depthTextureMode |= DepthTextureMode.Depth;

		sensorState = GenerateNonDepthRenTex(RenderTextureFormat.RGFloat);
		outputMap = GenerateNonDepthRenTex(RenderTextureFormat.RFloat);

		EventShader = AssetDatabase.LoadAssetAtPath<ComputeShader>(EventShaderAssetPath);
		eventKernel = EventShader.FindKernel("Main");

		EventShader.SetFloat("EventCountScale", DVConfig.EventCountScale);
		EventShader.SetFloat("ContrastThreshold", DVConfig.ContrastThreshold);
		EventShader.SetFloat("dtSecs", 1 / DVConfig.SimFPS);

		frameCapOut = GenerateNonDepthRenTex(RenderTextureFormat.ARGBFloat);
		frameCapTexture = new Texture2D(DVConfig.Resolution.x, DVConfig.Resolution.y, TextureFormat.RGBAFloat, false);

		FrameCapShader = AssetDatabase.LoadAssetAtPath<ComputeShader>(FrameCapShaderAssetPath);
		frameCapKernel = FrameCapShader.FindKernel("Main");

		// wont change so you can precompute this
		globalShaderGroups = Vector2Int.CeilToInt((Vector2)DVConfig.Resolution / 8f);

		events = new();
		events.Setup(camera);
		events.Open();
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
			DVConfig.Resolution.x,
			DVConfig.Resolution.y,
			0,
			format
		);
		tex.enableRandomWrite = true;
		tex.Create();

		return tex;
	}

	public void Cleanup() {
		if (camera != null)
			camera.targetTexture = null;

		Release(cameraTarget);
		Release(sensorState);
		Release(outputMap);
		Release(frameCapOut);
		Destroy(frameCapTexture);

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

		EventShader.SetTexture(eventKernel, "Camera", cameraTarget);
		EventShader.SetTexture(eventKernel, "State", sensorState);
		EventShader.SetTexture(eventKernel, "Output", outputMap);
		EventShader.SetBool("firstFrame", DVManager.Frame == 0);

		EventShader.Dispatch(eventKernel, globalShaderGroups.x, globalShaderGroups.y, 1);

		ulong timeAtReq = DVManager.Time;

		AsyncGPUReadback.Request(
			outputMap,
			0,
			TextureFormat.RFloat,
			req => Readback(req, timeAtReq)
		);

		if (DVConfig.DoFrameCaptures && (DVManager.Frame % (DVConfig.SimFPS / DVConfig.FrameCapFPS)) < 1f)
			TakeFrameCapture();
	}

	void Readback(AsyncGPUReadbackRequest request, ulong time) {
		if ((double)time / DVConfig.TimeScale * DVConfig.SimFPS < DVConfig.CameraWarmupTimeFrames) return;
		if (request.hasError) return;


		ulong dt = (ulong)math.round(DVConfig.TimeScale / DVConfig.SimFPS);

		NativeArray<float> outputData = request.GetData<float>();

		var eventQueue = new NativeQueue<Event>(Allocator.TempJob);

		var job = new ReadbackJob {
			OutputData = outputData,
			Events = eventQueue.AsParallelWriter(),

			Width = DVConfig.Resolution.x,
			Height = DVConfig.Resolution.y,

			Time = time,
			Dt = dt,

			EventCountScale = DVConfig.EventCountScale,
			ContrastThreshold = DVConfig.ContrastThreshold,
			InterpolateTime = DVConfig.InterpolateTime
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
		int frameCapFrameAtCall = (int)(DVManager.Frame * DVConfig.FrameCapFPS / DVConfig.SimFPS);

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
			DVConfig.OutputFolder,
			DVConfig.PermutationFolder,
			permutation,
			camera.name,
			DVConfig.FrameCapSubFolder);

		Directory.CreateDirectory(location);

		string fullPath = Path.Combine(location, $"{frame:D5}.exr");

		File.WriteAllBytes(fullPath, bytes);

	}

	public void ClearFrameCaptures(int[] permutation) {
		string permStr = string.Join('_', permutation);

		string location = Path.Combine(
			Application.dataPath,
			DVConfig.OutputFolder,
			DVConfig.PermutationFolder,
			permStr,
			camera.name,
			DVConfig.FrameCapSubFolder);

		if (Directory.Exists(location))
			Directory.Delete(location, true);
		Directory.CreateDirectory(location);
	}
}

[BurstCompile]
public struct ReadbackJob : IJobParallelFor {
	[ReadOnly] public NativeArray<float> OutputData;

	public NativeQueue<Event>.ParallelWriter Events;

	public int Width;
	public int Height;

	public ulong Time;
	public ulong Dt;

	public int EventCountScale;
	public float ContrastThreshold;
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

		ulong lastTime = Time;
		ulong t = Time;
		for (int n = 0; n < numEvents; n++) {

			if (InterpolateTime) {
				float crossing = polarity * (n + 1) * ContrastThreshold;
				float alpha = crossing / diff;
				t = Time + (ulong)math.round(alpha * Dt);

				if (t < lastTime + DVConfig.RefractoryPeriod) continue;
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