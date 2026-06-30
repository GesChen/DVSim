using System.Collections;
using System.Collections.Generic;
using UnityEngine;
public static class DVConfig {

	// --- Sensor Settings ---

	// global resolution for sim
	public static readonly Vector2Int Resolution = new(1280, 720);

	// simulated fps 10k-100k realistic.
	// make it 1m if you have all the time in the world i guess.
	// higher = better temporal precision, more realistic
	public const float SimFPS = 1000;

	public const int TimeScale = 1_000_000_000;

	public const bool InterpolateTime = true;

	public const int RefractoryPeriod = 10000; // global timescale, this is ns

	public const float tauOn = .005f;
	public const float tauOff = .010f;

	// v2e values
	public const float threshSigma = .05f;
	public const float idealPosThresh = .2f;
	public const float idealNegThresh = .2f;
	public const bool doLeaking = true;
	public const float noiseRateCovDecades = .1f;

	// --- Unity side config ---

	// scene warmup time frames
	public const int CameraWarmupTimeFrames = 50;

	// buffer initial capacity
	public const int EventBufferInitCap = 100000;

	// buffer flush interval
	public const int EventFlushIntervalMs = 10;

	// coefficient for event count in the packed float output from compute
	public const int EventCountScale = 100;

	// event output folder
	public const string OutputFolder = ".Output";
	public const string PermutationFolder = "Permutations";

	// ------- frame captures ------
	public const bool DoFrameCaptures = true;

	public const float FrameCapFPS = 60;

	public const string FrameCapSubFolder = "frames";
}