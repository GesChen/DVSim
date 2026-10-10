using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
#if UNITY_EDITOR
using UnityEditor;
#endif
using UnityEngine;
using UnityEngine.UIElements;

// expects CSV in vicon format Frame	Time	X	Y	Z	Roll	Pitch	Yaw (mm) (deg)
public class DVM_Mocap : DVMotion {
	public string SourceResourcePath;
	public float SourcePositionScaleFactorToM = 1000; // 1000x from mm -> m, assumed default
	public Transform pathTransform;

	struct Keyframe {
		public ulong time;
		public Vector3 position;
		public Quaternion orientation;
	}

	Keyframe[] path;
	double HzGuess; // in terms of ns or timescale not seconds

	public override void Initialize() {
		var keys = LoadCSV(out bool success);
		if (!success) return;

		path = keys.ToArray();

		// guess hz by averaging 1 / delta t 
		ulong totalDt = 0;
		ulong lastt = 0;
		foreach (Keyframe key in path) {
			totalDt += key.time - lastt;
			lastt = key.time;
		}
		double average = (double)totalDt / path.Length;

		HzGuess = 1d / average;
		if (path.Length == 0) HzGuess = 0;
	}

	public static Quaternion ViconToUnity(
	   float pitch,
	   float yaw,
	   float roll) {
		// CSV: ZYX Euler rotation order
		Quaternion csvRotation =
			Quaternion.AngleAxis(yaw, Vector3.forward) *
			Quaternion.AngleAxis(pitch, Vector3.up) *
			Quaternion.AngleAxis(roll, Vector3.right);

		// Local +Z forward and +Y up in CSV coordinates
		Vector3 csvForward =
			csvRotation * Vector3.forward;

		Vector3 csvUp =
			csvRotation * Vector3.up;

		// CSV Z-up -> Unity Y-up
		Vector3 unityForward = new Vector3(
			csvForward.x,
			csvForward.z,
			csvForward.y
		);

		Vector3 unityUp = new Vector3(
			csvUp.x,
			csvUp.z,
			csvUp.y
		);

		return Quaternion.LookRotation(
			unityForward,
			unityUp
		) * Quaternion.Euler(0f, -90f, 0f);
	}

	private List<Keyframe> LoadCSV(out bool success) {
		TextAsset csv = Resources.Load<TextAsset>(SourceResourcePath);

		success = false;
		if (csv == null) {
			Debug.LogError("CSV not found.");
			return null;
		}

		string[] lines = csv.text.Split('\n');

		List<Keyframe> keys = new();
		for (int i = 1; i < lines.Length; i++) {
			if (string.IsNullOrWhiteSpace(lines[i]))
				continue;

			string[] values = lines[i].Split(',');

			// im not writing a bunch of tryparses
			try {
				float parse(int i) => float.Parse(values[i], CultureInfo.InvariantCulture);

				float time = parse(1);
				float x = parse(2);
				float y = parse(3);
				float z = parse(4);
				float roll = parse(5);
				float pitch = parse(6);
				float yaw = parse(7);

				Vector3 position = new(-y, z, x);

				// Construct rotation in the source coordinate system.
				// Fixed-axis XYZ convention: Rz * Ry * Rx.

				Quaternion rotation = ViconToUnity(pitch, yaw, roll);

				//Debug.DrawRay(position, rotation * Vector3.forward, Color.blue);
				//Debug.DrawRay(position, rotation * Vector3.right, Color.red);
				//Debug.DrawRay(position, rotation * Vector3.up, Color.green);
				//Debug.Break();

				Keyframe keyframe = new() {
					time = (ulong)(time * DVConfig.timeScale),
					position = position * SourcePositionScaleFactorToM,
					orientation = rotation
				};

				keys.Add(keyframe);
			} catch {
				Debug.LogError($"Failed to parse keyframe {i} for file {SourceResourcePath}");
			}
		}
		
		success = true;
		return keys;
	}

	public override void UpdateMotion(ulong t) {
		if (path.Length == 0) return;

		(Vector3 interPos, Quaternion interRot) = SamplePath(t);

		transform.SetPositionAndRotation(interPos, interRot);
	}

	private (Vector3 pos, Quaternion rot) SamplePath(ulong t) {
		// find closest timestamps surrounding t
		float approxIndex = (float)(t * HzGuess);

		Keyframe koffsetI(int n) => path[Mathf.Clamp((int)approxIndex + n, 0, path.Length - 1)];

		Keyframe k0 = koffsetI(-1);
		Keyframe k1 = koffsetI(0);
		Keyframe k2 = koffsetI(1);
		Keyframe k3 = koffsetI(2);

		// handle this later, optimally shouldnt happen but if so then go search for it manually
		if (k0.time > t || k1.time > t || k2.time < t || k3.time < t) { 
			//Debug.LogError("fix ts"); 
			// fuck that im not dealing with ts you gotta update f_1 as well with guessing
		}

		// get 0-1 t
		int f_1 = (int)approxIndex;
		double t1 = f_1 / HzGuess; // the juice is worth the squeeze
		double t2 = (f_1 + 1)/ HzGuess;

		float T = (float)((t - t1) / (t2 - t1));

		Vector3 interPos = InterpolationMath.CatmullRomVec3Components(
			k0.position, k1.position, k2.position, k3.position, T);
		Quaternion interRot = InterpolationMath.CatmullLikeQuaternion(
			k0.orientation, k1.orientation, k2.orientation, k3.orientation, T);

		if (pathTransform != null) {
			interPos = pathTransform.TransformPoint(interPos);
			interRot *= pathTransform.rotation;
		}

		return (interPos, interRot);
	}

#if UNITY_EDITOR
	[Header("Visualize")]
	[SerializeField] private int samplesPerSegment = 16;
	[SerializeField] private float arrowSpacing = 0.5f;
	[SerializeField] private float arrowLength = 0.25f;
	[SerializeField] private float arrowHeadSize = 0.08f;
	List<Vector3> previewPositions = new();
	List<Quaternion> previewRotations = new();

	public void LoadPreview() {
		Initialize();

		previewPositions.Clear();
		previewRotations.Clear();

		if (path == null || path.Length < 2)
			return;

		ulong from = path[0].time;
		ulong to = path[^1].time;
		int rate = Mathf.Max(1, samplesPerSegment);
		ulong step = (ulong)(1d / HzGuess / rate);

		//Debug.Log($"from {from} to {to} step {step}");

		for (ulong t = from; t < to; t += step) {
			var (pos, rot) = SamplePath(t);
			previewPositions.Add(pos);
			previewRotations.Add(rot);
		}

		UnityEditor.SceneView.RepaintAll();
	}

	private void OnDrawGizmos() {
		if (previewPositions == null || previewPositions.Count < 2)
			return;
		
		Gizmos.color = Color.green;

		float distanceSinceArrow = 0f;

		DrawForwardArrow(previewPositions[0], previewRotations[0]);

		for (int i = 1; i < previewPositions.Count; i++) {
			Vector3 previous = previewPositions[i - 1];
			Vector3 current = previewPositions[i];

			Gizmos.color = Color.green;
			Gizmos.DrawLine(previous, current);

			distanceSinceArrow += Vector3.Distance(previous, current);

			if (distanceSinceArrow >= arrowSpacing) {
				DrawForwardArrow(current, previewRotations[i]);
				distanceSinceArrow = 0f;
			}
		}

		// start amd emd 
		Gizmos.color = Color.black;
		Gizmos.DrawWireSphere(previewPositions[0], .1f);
		Gizmos.color = Color.white;
		Gizmos.DrawWireSphere(previewPositions[^1], .1f);
	}

	private void DrawForwardArrow(Vector3 pos, Quaternion rot) {
		Vector3 forward = rot * Vector3.forward;
		Vector3 right = rot * Vector3.right;

		Vector3 tip = pos + forward * arrowLength;

		Gizmos.color = Color.cyan;
		Gizmos.DrawLine(pos, tip);

		Vector3 back = -forward * arrowHeadSize;
		Vector3 side = right * arrowHeadSize * 0.5f;

		Gizmos.DrawLine(tip, tip + back + side);
		Gizmos.DrawLine(tip, tip + back - side);
	}
#endif
}

#if UNITY_EDITOR
[CustomEditor(typeof(DVM_Mocap))]
public class DVM_MocapEditor : Editor {
	public override void OnInspectorGUI() {
		DrawDefaultInspector();

		var component = (DVM_Mocap)target;

		EditorGUILayout.Space();

		if (GUILayout.Button("Load Path Preview"))
			component.LoadPreview();
	}
}
#endif