using System.Collections;
using System.Collections.Generic;
using UnityEngine;
public static class DVConfig {
	public static uint Seed; // set by manager each run 

	// --- Sensor Settings ---

	// global resolution for sim
	public static readonly Vector2Int resolution = new(1280, 720);

	// simulated fps 10k-100k realistic.
	// make it 1m if you have all the time in the world i guess.
	// higher = better temporal precision, more realistic
	public const float simFPS = 1000;

	public const int timeScale = 1_000_000_000;

	public const bool interpolateTime = true;

	public const int refractoryPeriod = 10000; // global timescale, this is ns

	public const float tauOn = .005f;
	public const float tauOff = .010f;

	// v2e values
	public const float threshSigma = .05f;
	public const float idealPosThresh = .2f;
	public const float idealNegThresh = .2f;
	public const bool doLeaking = true;
	public const float noiseRateCovDecades = .1f;
	public const float leakRateHz = .1f;
	public const float leakJitterFraction = .1f;

	// --- Unity side config ---

	// scene warmup time frames
	public const int cameraWarmupTimeFrames = 50;

	// buffer initial capacity
	public const int eventBufferInitCap = 100000;

	// buffer flush interval
	public const int eventFlushIntervalMs = 10;

	// coefficient for event count in the packed float output from compute
	public const int eventCountScale = 100;

	// event output folder
	public const string outputFolder = ".Output";
	public const string permutationFolder = "Permutations";

	// ------- frame captures ------
	public const bool doFrameCaptures = true;

	public const float frameCapFPS = 60;

	public const string frameCapSubFolder = "frames";
	public const int frameNumPadDigits = 5;
}