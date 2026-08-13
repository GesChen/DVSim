using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public class DVManager : Singleton<DVManager> {
	[Header("Simulation")]
	public ulong Frame; 
	public ulong Time; // ns
	public bool Playing;
	public System.Diagnostics.Stopwatch Stopwatch;

	public List<DVVariable> Variables;

	public List<DVS> Sensors;
	public List<DVObject> ImmediateObjects;
	public bool PermZeroTestRun;

	[Header("Scene")]
	public Transform Scene;
	public Transform ArmatureGroup;
	public DVO_Armature[] Armatures;
	public DVO_Armature ArmatureInUse;

	[HideInInspector] public double CurrentSceneLengthSeconds;
	
	public int[] CurrentPermutation { get; private set; }
	public List<int[]> SubPermutations { get; private set; } = new();

	public void Tick() {
		foreach (var obj in ImmediateObjects) {
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

		PrecomputeAllCurObjIDs();

		if (PermZeroTestRun) {
			LoadPermutation(Enumerable.Repeat(0, Variables.Count).ToArray(), 0);

			StartCoroutine(SimulateCurrentScene());
		}
	}

	void InitSensors() {
		foreach (var sensor in Sensors) {
			if (sensor.gameObject.activeSelf)
				sensor.Init();
		}
	}

	void LoadPermutation(int[] permutation, int iteration) {
		if (permutation.Length != Variables.Count) {
			Debug.LogError("Cannot load permutation: incorrect permutation array length");
			return;
		}

		CurrentPermutation = permutation;

		Armatures = ArmatureGroup.GetComponentsInChildren<DVO_Armature>();

		ImmediateObjects.Clear();
		SubPermutations.Clear();

		for (int i = 0; i < permutation.Length; i++) {
			DVVariable variable = Variables[i];
			variable.ApplySubPermutation(permutation[i], iteration);

			SubPermutations.Add(variable.activeObjects);
			ImmediateObjects.AddRange(variable.activeObjects
				.Select(i => variable.Objects[i]).ToArray());
		}

		// very specific order

		// init animation
		foreach (var obj in ImmediateObjects)
			if (obj is DVO_PoseAnim anim) {
				// find armature type from the animation
				string tatype = anim.TargetArmatureType;
				ArmatureInUse = Armatures.First(a => a.Type == tatype);

				anim.Init();
				CurrentSceneLengthSeconds = (double)anim.Animation.Poses.Length / anim.Animation.fps;
				break;
			}
		
		// init humanmodel
		foreach (var obj in ImmediateObjects) 
			if (obj is DVO_HumanModel model) {
				model.Init();
				model.SetToCurArmature();
				break;
			}


		foreach (var obj in ImmediateObjects) {
			obj.Init();
		}
	}

	IEnumerator SimulateCurrentScene() {
		Frame = 0;

		Stopwatch = new();
		Stopwatch.Start();

		yield return null;

		PrepareAllSensors();

		try {
			Playing = true;
			while (Time < CurrentSceneLengthSeconds * DVConfig.timeScale) {
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
	
	public void PrecomputeAllCurObjIDs() {
		// only static ones, not new sub objects from instantiation
		var allCurObjs = Scene.GetComponentsInChildren<DVObject>(true);

		foreach (var obj in allCurObjs) {
			obj.GenerateID();
		}
	}

	public void LoadLighting(DVO_Lighting lighting) {
		foreach (var obj in ImmediateObjects) {
			if (obj is DVO_Lighting lightingObj)
				lightingObj.gameObject.SetActive(false);
		}

		lighting.gameObject.SetActive(true);
		lighting.Init();
		Debug.Log($"Loaded lighting \"{lighting.Label}\"");
	}

	// if this causes lag, implement a cache system for repeated same frame calls to this
	public List<DVObject> GetAllDVObjectsThisFrame() {
		var objs = ImmediateObjects.ToList();
		foreach (var imo in ImmediateObjects) {
			objs.AddRange(imo.GetSubObjects());
		}

		return objs;
	}
}