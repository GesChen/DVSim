using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class DVO_Lighting : DVObject {

	const bool SimulateIndirectBouncing = false;
	const int SIBounces = 2;

	// really arbitrary number that just means higher=slower and lower=faster but worse
	const int SIQuality = 50;
	const float SIMinLightDist = 1f;
	const float SISurfaceDist = 1f;
	const float SILightRange = 15;

	public override void Init() {
		if (SimulateIndirectBouncing) {
			var spotlights = GetComponentsInChildren<Light>().Where(l => l.type == LightType.Spot);

			foreach (var light in spotlights) {
				SimulateIndirect(light);
			}
		}
	}

	void SimulateIndirect(Light light) {
		float halfAngle = light.spotAngle * .5f;


		List<RaycastHit> hitPoints = new();
		for (int i = 0; i < SIQuality; i++) {
			float angle = (float)i / SIQuality;

			Ray ray = SimulateConeLightRay(1, angle, halfAngle, light.transform);
			if (Physics.Raycast(ray, out var hit)) 
				hitPoints.Add(hit);
		}

		EnforceMinDistance(hitPoints, SIMinLightDist);

		foreach (var hitPoint in hitPoints)
			GenerateSILight(hitPoint, light);

		Debug.Break();
	}


	static Ray SimulateConeLightRay(float radius, float angle, float lightHalfAngle, Transform light) {
		float theta = radius * lightHalfAngle * Mathf.Deg2Rad;
		float phi = angle * Mathf.PI * 2f;

		float sinTheta = Mathf.Sin(theta);
		Vector3 localRot = new(
		sinTheta * Mathf.Cos(phi),
		sinTheta * Mathf.Sin(phi),
		Mathf.Cos(theta));

		return new Ray(light.position, light.rotation * localRot);
	}

	static void EnforceMinDistance(List<RaycastHit> points, float minDist) {
		float minDist2 = minDist * minDist;

		// Optional: randomize before pruning to avoid original-order bias.
		for (int i = points.Count - 1; i > 0; i--) {
			int j = Random.Range(0, i + 1);
			(points[i], points[j]) = (points[j], points[i]);
		}

		List<RaycastHit> kept = new();

		foreach (var p in points) {
			bool valid = true;

			foreach (RaycastHit k in kept) {
				if ((p.point - k.point).sqrMagnitude < minDist2) {
					valid = false;
					break;
				}
			}

			if (valid)
				kept.Add(p);
		}

		points.Clear();
		points.AddRange(kept);
	}

	void GenerateSILight(RaycastHit hit, Light original) {
		float intensity = original.intensity / Mathf.Max((hit.distance * hit.distance), 1e-5f);

		Renderer renderer = hit.collider.GetComponent<Renderer>();
		Material mat = renderer.sharedMaterial;

		Texture2D tex = mat.GetTexture("_BaseMap") as Texture2D;
		Color tint = mat.GetColor("_BaseColor");

		Color albedo = tex != null
			? tex.GetPixelBilinear(hit.textureCoord.x, hit.textureCoord.y) * tint
			: tint;

		var newObj = new GameObject("Simulated Indirect");
		newObj.transform.SetParent(original.transform);
		newObj.transform.position = hit.point + hit.normal * SISurfaceDist;
		
		var light = newObj.AddComponent<Light>();
		light.type = LightType.Point;
		light.intensity = intensity;
		light.color = original.color * albedo;
		light.range = SILightRange;
	}

	public override void UpdateState(ulong time) {
		
	}
}