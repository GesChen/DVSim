using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEditor;
using System;

public abstract class DVO_VehicleLOD : MonoBehaviour {
	public int[] BBoxKeypoints;

	[HideInInspector] public Renderer renderer;
	[HideInInspector] public Material material;
	Vector3[] keypoints;
	public virtual void Init() {
		renderer = GetComponent<Renderer>();
		Vector3[] vertices = GetComponent<MeshFilter>().mesh.vertices;
		keypoints = BBoxKeypoints.Select(k => vertices[k]).ToArray(); // one copy
		if (Application.isPlaying)
			material = renderer.material;
	}

	public virtual DVSMemory.InterBBox GenerateBBox(Camera camera) {
		if (renderer == null) return null;

		Vector3[] wsVerts = keypoints.ToArray();
		transform.TransformPoints(wsVerts);

		Vector2 min = Vector2.positiveInfinity;
		Vector2 max = Vector2.negativeInfinity;
		Vector3 total = Vector3.zero;

		foreach (Vector3 v3 in wsVerts) {
			Vector2 v2 = camera.WorldToScreenPoint(v3);

			min = Vector2.Min(min, v2);
			max = Vector2.Max(max, v2);
			total += v3;
			//DebugExtra.DrawPoint(v3, duration: .1f);
		}
		Vector3 center = total / wsVerts.Length;
		//DebugExtra.DrawRectSS(min, max, camera, drawGame: true, duration: .3f);

		return new() {
			min = min,
			max = max,
			dist = (camera.transform.position - center).magnitude
		};
	}
}

// multi object editing not supported BLAH BLAH WTF????
// im so tired im putting this bullshit in by hand
/*
[CustomEditor(typeof(DVO_VehicleLOD), true)]
public class VLODEditor : Editor {
	public override void OnInspectorGUI() {
		DrawDefaultInspector();
		DVO_VehicleLOD myScript = (DVO_VehicleLOD)target;
		if (GUILayout.Button("Paste bbox keypoints")) {
			myScript.BBoxKeypoints = 
				GUIUtility.systemCopyBuffer.TrimStart('[').TrimEnd(']').Split(',').Select(s => int.Parse(s.Trim())).ToArray();
		}
	}
}*/