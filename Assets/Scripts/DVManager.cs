using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class DVManager : Singleton<DVManager> {
	public static ulong Frame; 
	public static ulong Time; // ns

	[Serializable]
	public class PermutationGroup {
		public string Category;
		public List<DVObject> Objects;
	}

	public List<PermutationGroup> PermutationGroups;

	public List<DVS> Sensors;
	public List<DVObject> Objects;

	public void Tick() {
		Frame++;
		Time = (ulong)Math.Round(Frame * DVConfig.TimeScale / DVConfig.SimFPS);

		foreach (var obj in Objects) {
			obj.UpdateState(Time);
		}
		
		foreach (var sensor in Sensors) {
			sensor.Tick();
		}

	}

	private void Start() {
		InitSensors();

		LoadPermutation(new int[] { 0, 0, 0, 0, 0 });

		StartCoroutine(SimulateCurrentScene());
	}

	private void OnDisable() {
		CleanupCurrentScene();
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

		while (Time < SceneManager.Instance.CurrentSceneLengthSeconds * DVConfig.TimeScale) {
			Tick();

			// dont freeze the player
			yield return new WaitForEndOfFrame();
		}

		CleanupCurrentScene();
	}

	void CleanupCurrentScene() {
		foreach (var sensor in Sensors)
			sensor.Cleanup();
	}
}