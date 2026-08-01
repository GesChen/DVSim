using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using Unity.Mathematics;
using UnityEditor;
using UnityEngine;

public class DVManager : Singleton<DVManager> {
	public ulong Frame; 
	public ulong Time; // ns
	public bool Playing;
	public System.Diagnostics.Stopwatch Stopwatch;

	public List<DVPermutationGroup> PermutationGroups;

	public List<DVS> Sensors;
	public List<DVObject> Objects;
	public bool PermZeroTestRun;

	public static int[] CurrentPermutation { get; private set; }

	public void Tick() {
		foreach (var obj in Objects) {
			obj.UpdateState(Time);
		}

		foreach (var sensor in Sensors) {
			if (sensor.gameObject.activeSelf)
				sensor.Tick(Time);
		}

		Frame++;
		Time = (ulong)Math.Round(Frame * DVConfig.timeScale / DVConfig.simFPS);
	}

	private void Start() {
		Frame = 0;
		Time = 0;

		EditorApplication.playModeStateChanged += state => {
			if (state == PlayModeStateChange.ExitingPlayMode) {
				Playing = false;
			}
		};

		var random = new System.Random();
		DVConfig.Seed = random.Next(int.MinValue, int.MaxValue);

		InitSensors();

		if (PermZeroTestRun) {
			LoadPermutation(new int[] { 0, 0, 0, 0, 0, 0 });

			StartCoroutine(SimulateCurrentScene());
		}
	}

	void InitSensors() {
		foreach (var sensor in Sensors) {
			if (sensor.gameObject.activeSelf)
				sensor.Init();
		}
	}

	void LoadPermutation(int[] permutation) {
		if (permutation.Length != PermutationGroups.Count) {
			Debug.LogError("Cannot load permutation: incorrect permutation array length");
			return;
		}

		CurrentPermutation = permutation;

		Objects = SceneManager.Instance.SetSceneFromPermutation(permutation, PermutationGroups);

		// idk whether to put inits in here or start of simulate coroutine
		foreach (var obj in Objects) {
			obj.Init();
		}

		SceneManager.Instance.InitializeHumanModel(Objects);

		// bad code but oh well
		DVO_PoseAnim anim = null;
		foreach (var obj in Objects) {
			if (obj.TryGetComponent(out DVO_PoseAnim an))
				anim = an;
		}
		if (anim == null) {
			Debug.LogError("No animation found in the current permutation!");
			return;
		}
		
		SceneManager.Instance.CurrentSceneLengthSeconds = (double)anim.Animation.Poses.Length / anim.Animation.fps;
	}

	IEnumerator SimulateCurrentScene() {
		Frame = 0;

		Stopwatch = new();
		Stopwatch.Start();

		yield return null;

		PrepareAllSensors();

		try {
			Playing = true;
			while (Time < SceneManager.Instance.CurrentSceneLengthSeconds * DVConfig.timeScale) {
				if (Playing)
					Tick();
				else
					break;

				// dont freeze the player
				yield return new WaitForEndOfFrame();
			}
			Playing = false;
		} finally { // ensure cleanup occurs
			CleanupSensors();
		}
	}

	private void OnDisable() {
		CleanupSensors();
	}

	protected override void OnDestroy() {
		CleanupSensors();

		base.OnDestroy();
	}

	private void OnApplicationQuit() {
		CleanupSensors();
	}

	void CleanupSensors() {
		foreach (var sensor in Sensors) {
			if (sensor == null) continue;

			if (sensor.gameObject.activeSelf)
				sensor.Cleanup();
		}
	}

	void PrepareAllSensors() {
		foreach (var sensor in Sensors)
			if (sensor.gameObject.activeSelf)
				sensor.Prepare(CurrentPermutation);
	}
}