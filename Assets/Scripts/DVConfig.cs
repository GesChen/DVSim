using System.Collections;
using System.Collections.Generic;
using UnityEngine;
public static class DVConfig {
	// global resolution for sim
	public static readonly Vector2Int Resolution = new(1280, 720);

	// simulated fps 10k-100k realistic.
	// make it 1m if you have all the time in the world i guess.
	// higher = better temporal precision, more realistic
	public const float SimFPS = 100;

	// global time scale
	public const int TimeScale = 1_000_000_000;

	// contrast threshold realistic .1 - .15
	public const float ContrastThreshold = .1f;

	// interpolate t for better accuracy?
	public const bool InterpolateTime = true;

	// scene warmup time frames
	public const int CameraWarmupTimeFrames = 50;

	// buffer initial capacity
	public const int EventBufferInitCap = 100000;

	// buffer flush interval
	public const int EventFlushIntervalMs = 10;

	// event output folder
	public const string DataFolder = ".Output";
	public const string PermutationFolder = "Permutations";

	// ------- frame captures ------
	public const bool DoFrameCaptures = true;

	public const float FrameCapFPS = 60;

	public const string FrameCapSubFolder = "frames";
}