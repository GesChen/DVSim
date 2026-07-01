using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using System;

public class DVManager : Singleton<DVManager> {
	public static ulong Frame; 
	public static ulong Time; // ns
	public static bool Playing;

	[Serializable]
	public class PermutationGroup {
		public string Category;
		public List<DVObject> Objects;
	}

	public List<PermutationGroup> PermutationGroups;

	public List<DVS> Sensors;
	public List<DVObject> Objects;

	public static int[] CurrentPermutation { get; private set; }

	public void Tick() {
		foreach (var obj in Objects) {
			obj.UpdateState(Time);
		}

		foreach (var sensor in Sensors) {
			sensor.Tick();
		}

		Frame++;
		Time = (ulong)Math.Round(Frame * DVConfig.timeScale / DVConfig.simFPS);
	}

	private void Start() {
		Frame = 0;
		Time = 0;

		InitSensors();

		LoadPermutation(new int[] { 0, 0, 0, 0, 0 });

		StartCoroutine(SimulateCurrentScene());

		EditorApplication.playModeStateChanged += state => {
			if (state == PlayModeStateChange.ExitingPlayMode) {
				Playing = false;
			}
		};
	}

	void InitSensors() {
		foreach (var sensor in Sensors) {
			sensor.Init();
		}
	}

	void LoadPermutation(int[] permutation) {
		if (permutation.Length != PermutationGroups.Count) {
			Debug.LogError("Cannot load permutation: incorrect permutation array length");
			return;
		}

		CurrentPermutation = permutation;

		Objects = SceneManager.Instance.CreateSceneFromPermutations(permutation, PermutationGroups);

		// idk whether to put inits in here or start of simulate coroutine
		foreach (var obj in Objects) {
			obj.Init();
		}

		// bad code but oh well
		var anim = SceneManager.Instance.AnimationContainer.GetComponentInChildren<DVO_PoseAnim>();
		SceneManager.Instance.CurrentSceneLengthSeconds = (double)anim.Animation.Poses.Length / anim.Animation.fps;
	}

	IEnumerator SimulateCurrentScene() {
		Frame = 0;
		ClearAllSensorFrames();

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

		CleanupCurrentScene();
	}

	void ClearAllSensorFrames() {
		foreach (var sensor in Sensors) {
			sensor.ClearFrameCaptures(CurrentPermutation);
		}
	}

	void CleanupCurrentScene() {
		foreach (var sensor in Sensors)
			sensor.Cleanup();
	}
}