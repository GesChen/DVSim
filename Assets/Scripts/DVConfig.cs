using System.Collections;
using System.Collections.Generic;
using UnityEngine;
public class DVConfig : MonoBehaviour {
	// global resolution for sim
	public static readonly Vector2Int Resolution = new(1280, 720);

	// simulated fps 10k-100k realistic.
	// make it 1m if you have all the time in the world i guess.
	// higher = better temporal precision, more realistic
	public const float SimFPS = 60;

	// global time scale
	public const int TimeScale = 1_000_000_000;

	// contrast threshold realistic .1 - .15
	public const float ContrastThreshold = .1f;

	// interpolate t for better accuracy?
	public const bool InterpolateTime = true;

	// scene warmup time ns
	public const ulong CameraWarmupTime = 1_000_000_000;

	// buffer capacity
	public const int EventBufferCap = 100000;

	// buffer flush threshold
	public const int EventBufferFlush = 80000;

	// event output folder
	public const string DataFolder = "Output";
}