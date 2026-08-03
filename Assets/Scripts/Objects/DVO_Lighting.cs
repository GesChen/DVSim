using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public class DVO_Lighting : DVObject {
	public enum EnvironmentLightingSource {
		Skybox,
		Gradient,
		Color
	}

	public enum EnvironmentReflectionSource {
		Skybox,
		Custom
	}

	[SerializeField] private Material skyboxMaterial;
	[SerializeField] private Light sunSource;
	[SerializeField] private Color realtimeShadowColor = Color.gray;

	[SerializeField]
	private EnvironmentLightingSource lightingSource =
		EnvironmentLightingSource.Skybox;

	[SerializeField] private Color skyColor = Color.gray;
	[SerializeField] private Color equatorColor = Color.gray;
	[SerializeField] private Color groundColor = Color.gray;
	[SerializeField] private Color ambientColor = Color.gray;

	[SerializeField, Range(0f, 8f)]
	private float environmentIntensityMultiplier = 1f;
	
	[SerializeField]
	private EnvironmentReflectionSource reflectionSource =
		EnvironmentReflectionSource.Skybox;

	[SerializeField] private Cubemap customCubemap;

	[SerializeField, Range(0f, 1f)]
	private float reflectionIntensityMultiplier = 1f;

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

		Load();
	}

	public void Load() {
		RenderSettings.skybox = skyboxMaterial;
		RenderSettings.sun = sunSource;
		RenderSettings.subtractiveShadowColor = realtimeShadowColor;

		switch (lightingSource) {
			case EnvironmentLightingSource.Skybox:
				RenderSettings.ambientMode = AmbientMode.Skybox;
				break;

			case EnvironmentLightingSource.Gradient:
				RenderSettings.ambientMode = AmbientMode.Trilight;
				RenderSettings.ambientSkyColor = skyColor;
				RenderSettings.ambientEquatorColor = equatorColor;
				RenderSettings.ambientGroundColor = groundColor;
				break;

			case EnvironmentLightingSource.Color:
				RenderSettings.ambientMode = AmbientMode.Flat;
				RenderSettings.ambientLight = ambientColor;
				break;
		}

		RenderSettings.ambientIntensity =
			environmentIntensityMultiplier;

		switch (reflectionSource) {
			case EnvironmentReflectionSource.Skybox:
				RenderSettings.defaultReflectionMode =
					DefaultReflectionMode.Skybox;

				RenderSettings.customReflectionTexture = null;
				break;

			case EnvironmentReflectionSource.Custom:
				RenderSettings.defaultReflectionMode =
					DefaultReflectionMode.Custom;

				RenderSettings.customReflectionTexture = customCubemap;
				break;
		}

		RenderSettings.reflectionIntensity =
			reflectionIntensityMultiplier;

		DynamicGI.UpdateEnvironment();
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


#if UNITY_EDITOR


[CustomEditor(typeof(DVO_Lighting))]
public sealed class DVOLightingConfigEditor : Editor {
	private SerializedProperty skyboxMaterial;
	private SerializedProperty sunSource;
	private SerializedProperty realtimeShadowColor;

	private SerializedProperty lightingSource;
	private SerializedProperty skyColor;
	private SerializedProperty equatorColor;
	private SerializedProperty groundColor;
	private SerializedProperty ambientColor;
	private SerializedProperty environmentIntensityMultiplier;

	private SerializedProperty reflectionSource;
	private SerializedProperty customCubemap;
	private SerializedProperty reflectionIntensityMultiplier;

	private void OnEnable() {
		skyboxMaterial =
			serializedObject.FindProperty("skyboxMaterial");

		sunSource =
			serializedObject.FindProperty("sunSource");

		realtimeShadowColor =
			serializedObject.FindProperty("realtimeShadowColor");

		lightingSource =
			serializedObject.FindProperty("lightingSource");

		skyColor =
			serializedObject.FindProperty("skyColor");

		equatorColor =
			serializedObject.FindProperty("equatorColor");

		groundColor =
			serializedObject.FindProperty("groundColor");

		ambientColor =
			serializedObject.FindProperty("ambientColor");

		environmentIntensityMultiplier =
			serializedObject.FindProperty(
				"environmentIntensityMultiplier"
			);

		reflectionSource =
			serializedObject.FindProperty("reflectionSource");

		customCubemap =
			serializedObject.FindProperty("customCubemap");

		reflectionIntensityMultiplier =
			serializedObject.FindProperty(
				"reflectionIntensityMultiplier"
			);
	}

	public override void OnInspectorGUI() {
		serializedObject.Update();

		EditorGUILayout.LabelField(
			"Environment",
			EditorStyles.boldLabel
		);

		EditorGUILayout.PropertyField(
			skyboxMaterial,
			new GUIContent("Skybox Material")
		);

		EditorGUILayout.PropertyField(
			sunSource,
			new GUIContent("Sun Source")
		);

		EditorGUILayout.PropertyField(
			realtimeShadowColor,
			new GUIContent("Realtime Shadow Color")
		);

		EditorGUILayout.Space();

		EditorGUILayout.LabelField(
			"Environment Lighting",
			EditorStyles.boldLabel
		);

		EditorGUILayout.PropertyField(
			lightingSource,
			new GUIContent("Source")
		);

		var selectedLightingSource =
			(DVO_Lighting.EnvironmentLightingSource)
			lightingSource.enumValueIndex;

		switch (selectedLightingSource) {
			case DVO_Lighting
				.EnvironmentLightingSource.Gradient:

				EditorGUILayout.PropertyField(
					skyColor,
					new GUIContent("Sky Color")
				);

				EditorGUILayout.PropertyField(
					equatorColor,
					new GUIContent("Equator Color")
				);

				EditorGUILayout.PropertyField(
					groundColor,
					new GUIContent("Ground Color")
				);

				break;

			case DVO_Lighting
				.EnvironmentLightingSource.Color:

				EditorGUILayout.PropertyField(
					ambientColor,
					new GUIContent("Ambient Color")
				);

				break;
		}

		EditorGUILayout.PropertyField(
			environmentIntensityMultiplier,
			new GUIContent("Intensity Multiplier")
		);

		EditorGUILayout.Space();

		EditorGUILayout.LabelField(
			"Environment Reflections",
			EditorStyles.boldLabel
		);

		EditorGUILayout.PropertyField(
			reflectionSource,
			new GUIContent("Source")
		);

		var selectedReflectionSource =
			(DVO_Lighting.EnvironmentReflectionSource)
			reflectionSource.enumValueIndex;

		if (selectedReflectionSource ==
			DVO_Lighting
				.EnvironmentReflectionSource.Custom) {
			EditorGUILayout.PropertyField(
				customCubemap,
				new GUIContent("Cubemap")
			);
		}

		EditorGUILayout.PropertyField(
			reflectionIntensityMultiplier,
			new GUIContent("Intensity Multiplier")
		);

		serializedObject.ApplyModifiedProperties();
	}
}

#endif