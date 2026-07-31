using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Converters;

public static class DVConfig {
	public static int Seed; // set by manager each run 

	// --- Sensor Settings ---

	// global resolution for sim
	public static readonly Vector2Int resolution = new(1280, 720);

	public const float DefaultStereoSpacing = .065f; // 65 mm, typical spacing

	// simulated fps 10k-100k most realistic.
	// make it 1m if you have all the time in the world i guess.
	// higher = better temporal precision, more realistic
	public const float simFPS = 100; 
	public const int timeScale = 1_000_000_000;
	public const bool interpolateTime = true;
	public const int refractoryPeriod = 10000; // global timescale, this is ns

	// low pass filter settings 
	public const float tauOn = .005f; // has to be in seconds 
	public const float tauOff = .010f;

	// v2e noise values
	public const float threshSigma = .05f;
	public const float idealPosThresh = .2f;
	public const float idealNegThresh = .2f;
	public const float noiseRateCovDecades = .1f;
	public const bool doLeaking = true;
	public const float leakRateHz = .1f;
	public const float leakJitterFraction = .1f;

	[Newtonsoft.Json.JsonConverter(typeof(StringEnumConverter))]
	public enum PhotoNoiseBehaviour {
		None,
		v2e,
		FixedVolts,
		ApproximatedBA // approximate voltage based on background activity
	}
	public const PhotoNoiseBehaviour photoNoise = PhotoNoiseBehaviour.None;

	// v2e calculation
	public const float shotNoiseRateHz = 5f;
	// this value is REALLY finnicky. try to figure it out better. 
	public const float photoNoiseCutoffHz = 100; // for 1000fps 100-300, no longer v2e's

	public const float fixedPhotoNoiseVolts = .09f; // 1 mV

	public const float targetBA = .1f;

	// --- Unity side config ---
	public const int cameraWarmupTimeFrames = 50; // scene warmup time frames
	public const int eventBufferInitCap = 100000; // buffer initial capacity
	public const int eventFlushIntervalMs = 10; // buffer flush interval
	public const int eventCountScale = 100; // coefficient for event count in the packed float output from compute
	public const bool doAutoGrounding = true;

	// --- output ---
	public const string outputFolder = ".Output"; // event output folder
	public const string permutationFolder = "Permutations";

	public const string metadataFileName = "meta.json";

	// -- extra data --
	public const float extraDataSampleRate = 100;
	public const bool recordCameraRoute = true;
	public const string camRouteFileName = "cameraroute.json";

	//public const bool recordSkeleton = true;
	//public const string skeletonFileName = "skeleton.json";

	public const bool recordBboxes = true;
	public const string bboxFileName = "bboxes_raw.json";

	// ------- frame captures ------
	public const bool doFrameCaptures = true;
	public const bool useEXR = false; // easy to debug, takes longer to encode
	public const float frameCapFPS = 60;

	public const string frameCapSubFolder = "frames";
	public const string frameCapDataSubFolder = "data";
	public const int frameNumDigits = 5;
	public const bool deleteFrameCapsAfterPostProcess = false;
}