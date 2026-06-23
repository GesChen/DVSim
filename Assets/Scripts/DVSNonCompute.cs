using System;
using System.Collections;
using System.Collections.Generic;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Rendering;

[DisallowMultipleComponent]
public class DVSNonCompute : MonoBehaviour {
	Camera camera;
	RenderTexture target;
	DVSEventBuffer events;

	class Frame {
		public float[][] value;

		public Frame() {
			(int width, int height) = (DVConfig.Resolution.x, DVConfig.Resolution.y);

			value = new float[height][];

			for (int y = 0; y < height; y++) {
				value[y] = new float[width];

				for (int x = 0; x < width; x++) {
					value[y][x] = 0;
				}
			}
		}

		public Frame(NativeArray<Color> pixels) {
			(int width, int height) = (DVConfig.Resolution.x, DVConfig.Resolution.y);

			value = new float[height][];

			for (int y = 0; y < height; y++) {
				value[y] = new float[width];

				for (int x = 0; x < width; x++) {
					Color col = pixels[y * width + x];

					value[y][x] = LogLuma(col);
				}
			}
		}

		float LogLuma(Color col) {
			float r = Mathf.Max(0f, col.r);
			float g = Mathf.Max(0f, col.g);
			float b = Mathf.Max(0f, col.b);

			float luma =
				0.2126f * r +
				0.7152f * g +
				0.0722f * b;
			luma = Mathf.Max(luma, 1e-4f); // no zero logging

			return Mathf.Log(luma);
		}

		public float Get(int x, int y) => value[y][x];
		public void Set(int x, int y, float val) {
			value[y][x] = val;
		}
	}

	Frame LogReference;

	private void Awake() {
		target = new(
			DVConfig.Resolution.x,
			DVConfig.Resolution.y,
			24,
			RenderTextureFormat.ARGBHalf
		);
		target.Create();

		camera = GetComponent<Camera>();
		camera.allowHDR = true;
		camera.targetTexture = target;

		events = new();
		events.Setup(transform.name);
	}

	public void Tick() {
		AsyncGPUReadback.Request(
			target,
			0,
			TextureFormat.RGBAFloat,
			req => Readback(req, DVManager.Time)
		);
	}

	void Readback(AsyncGPUReadbackRequest req, ulong time) {
		if (req.hasError) {
			Debug.LogError("Readback failed"); return;
		}

		var pixels = req.GetData<Color>();
		
		// convert to frame of log luma vals
		var frame = new Frame(pixels);

		// hack because fsr the first 2 frames are black 
		if (time > DVConfig.CameraWarmupTime)
			Compare(frame, time);
	}

	void Compare(Frame frame, ulong time) {
		// initialize lr to frame to prevent event burst
		LogReference ??= frame;

		ulong dt = (ulong)Math.Round(1_000_000_000.0 / DVConfig.SimFPS);

		for (int y = 0; y < DVConfig.Resolution.y; y++) {
			for (int x = 0; x < DVConfig.Resolution.x; x++) {
				float last = LogReference.Get(x, y);
				float li = frame.Get(x, y);

				// calculate diff and event count
				float diff = li - last;

				bool on = diff > 0;
				int polarity = on ? 1 : -1;

				int numEvents = Mathf.FloorToInt(polarity * diff / DVConfig.ContrastThreshold);
				if (numEvents <= 0) continue;

				Debug.Log($"generating {numEvents} events at {x} {y} time {time}");

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

				// update logref
				LogReference.Set(x, y,
					last + polarity * numEvents * DVConfig.ContrastThreshold);

			}
		}
	}
}