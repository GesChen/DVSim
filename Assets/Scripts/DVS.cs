using System;
using System.Collections;
using System.Collections.Generic;
using Unity.Burst;
using Unity.Collections;
using Unity.Jobs;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using Unity.Mathematics;


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
	RenderTexture logReference;
	RenderTexture outputMap;

	ComputeShader Shader;
	int kernel;

	Vector2Int groups;

	private void Awake() {

		cameraTarget = new(
			DVConfig.Resolution.x,
			DVConfig.Resolution.y,
			24,
			RenderTextureFormat.ARGBHalf
		);
		cameraTarget.Create();

		camera = GetComponent<Camera>();
		camera.allowHDR = true;
		camera.targetTexture = cameraTarget;

		logReference = GenerateNonDepthRenTex(RenderTextureFormat.RFloat);
		outputMap = GenerateNonDepthRenTex(RenderTextureFormat.RFloat);

		Shader = AssetDatabase.LoadAssetAtPath<ComputeShader>(
			"Assets/Scripts/DVCalc.compute"
		);

		kernel = Shader.FindKernel("Main");

		// wont change so you can precompute this
		groups = Vector2Int.CeilToInt((Vector2)DVConfig.Resolution / 8f);

		events = new();
		events.Setup(transform.name);
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


	private void OnDestroy() {
		Release(cameraTarget);
		Release(logReference);
		Release(outputMap);
	}

	private void Release(RenderTexture rt) {
		if (rt == null)
			return;

		rt.Release();
	}

	public void Tick() {
		Shader.SetTexture(kernel, "Camera", cameraTarget);
		Shader.SetTexture(kernel, "LogReference", logReference);
		Shader.SetTexture(kernel, "Output", outputMap);
		Shader.SetFloat("ContrastThreshold", DVConfig.ContrastThreshold);

		Shader.Dispatch(kernel, groups.x, groups.y, 1);

		AsyncGPUReadback.Request(
			outputMap,
			0,
			TextureFormat.RFloat,
			req => ReadbackBurst(req, DVManager.Time)
		);
	}

	void Readback(AsyncGPUReadbackRequest request, ulong time) {
		if (time < DVConfig.CameraWarmupTime) return;

		ulong dt = (ulong)Math.Round(1_000_000_000.0 / DVConfig.SimFPS);

		var outputData = request.GetData<float>();

		// scan output for events
		int index = 0;
		for (int y = 0; y < DVConfig.Resolution.y; y++) {
			for (int x = 0; x < DVConfig.Resolution.x; x++) {

				float data = outputData[index++];

				// extract compressed data from the single float
				int numEvents = Mathf.Abs(Mathf.FloorToInt(data / 100f));
				int polarity = (int)Mathf.Sign(data);
				float diff = polarity * (data - numEvents * 100f);
				bool on = diff > 0;

				// generate events
				for (int n = 0; n < numEvents; n++) {

					ulong t = time;
					if (DVConfig.InterpolateTime) {
						// estimate crossing point based on intensity 
						// assuming linear luma change between frames
						float crossing = polarity * (n + 1) * DVConfig.ContrastThreshold;
						float alpha = crossing / diff;

						// interpolated time also accounts for multi event bursts
						t = time + (ulong)Math.Round(alpha * dt);
					}

					events.NewEvent(x, y, t, on);
				}
			}
		}
	}

	void ReadbackBurst(AsyncGPUReadbackRequest request, ulong time) {
		if (time < DVConfig.CameraWarmupTime)
			return;

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

			ContrastThreshold = DVConfig.ContrastThreshold,
			InterpolateTime = DVConfig.InterpolateTime
		};

		JobHandle handle = job.Schedule(outputData.Length, 128);
		handle.Complete();

		while (eventQueue.TryDequeue(out Event e)) {
			events.NewEvent(e.x, e.y, e.t, e.p);
		}

		eventQueue.Dispose();
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

	public float ContrastThreshold;
	public bool InterpolateTime;

	public void Execute(int index) {
		float data = OutputData[index];

		if (data == 0) return;

		int numEvents = math.abs((int)math.floor(data / 100f));

		int x = index % Width;
		int y = index / Width;

		bool on = data > 0f;
		int polarity = on ? 1 : -1;
		float diff = polarity * (math.abs(data) - numEvents * 100f);

		for (int n = 0; n < numEvents; n++) {
			ulong t = Time;

			if (InterpolateTime) {
				float crossing = polarity * (n + 1) * ContrastThreshold;
				float alpha = crossing / diff;
				t = Time + (ulong)math.round(alpha * Dt);
			}

			Events.Enqueue(new Event {
				x = x,
				y = y,
				t = t,
				p = on
			});
		}
	}
}