using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System.Linq;

public class DVO_PedestrianPart : DVO_VehicleLOD {
	SkinnedMeshRenderer smr;
	Mesh bakeMesh;
	List<Vector3> bakeVerts = new();

	public override void Init() {
		renderer = GetComponent<Renderer>();
		smr = GetComponent<SkinnedMeshRenderer>();
		bakeMesh = new Mesh { name = "Vertex Picker Baked Mesh" };
		if (Application.isPlaying)
			material = renderer.material;
	}

	public void Randomize(uint srcID) {
		int selection = (int)(srcID % DVO_Pedestrian.SMPLitexTextures.Length);

		if (Application.isPlaying)
			material.SetTexture("_BaseMap", DVO_Pedestrian.SMPLitexTextures[selection]);
	}

	public void UpdateState(ulong t) {

	}

	// this shit should be abstracted with humanmodel someday :( 
	// TODO: asd
	public override DVSMemory.InterBBox GenerateBBox(Camera camera) {
		if (renderer == null) return null;
		
		smr.BakeMesh(bakeMesh);
		bakeMesh.GetVertices(bakeVerts);

		Vector3[] wsVerts = BBoxKeypoints.Select(k => bakeVerts[k]).ToArray();
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