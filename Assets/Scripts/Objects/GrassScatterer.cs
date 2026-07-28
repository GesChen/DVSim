using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

#if UNITY_EDITOR
using UnityEditor;
#endif

[ExecuteAlways]
public class GrassScatterer : MonoBehaviour {
	[Header("Source")]
	[SerializeField] GameObject grassObjectGroup;
	[SerializeField] Camera densityCamera;

	[Header("Distribution")]
	[Tooltip("Approximate maximum grass instances per square unit.")]
	[Min(0.001f)]
	[SerializeField] float overallDensity = 4f;

	[Tooltip("Density multiplier: 1 / (1 + distance * falloff).")]
	[Min(0f)]
	[SerializeField] float distanceFalloff = 0.02f;

	[SerializeField] int poissonAttempts = 20;
	[SerializeField] int seed = 12345;

	[Header("Rotation")]
	[SerializeField] Vector2 yawRange = new Vector2(-180f, 180f);
	[SerializeField] float maximumTilt = 6f;

	[Header("Rendering")]
	[SerializeField] bool drawGrass = true;
	[SerializeField] bool castShadows = true;
	[SerializeField] bool receiveShadows = true;

	[Header("Readout")]
	[SerializeField, HideInInspector] int generatedInstances;
	[SerializeField, HideInInspector] int renderedInstances;
	[SerializeField, HideInInspector] long renderedVertexCount;

	const int MaxBatchSize = 1023;

	[Serializable]
	struct GrassSource {
		public Mesh mesh;
		public Material[] materials;
		public Vector3 scale;
		public Quaternion rotation;
	}

	struct GrassSample {
		public Vector3 position;
		public Quaternion rotation;
		public int sourceIndex;
		public float densityValue;
	}

	GrassSource[] sources = Array.Empty<GrassSource>();
	GrassSample[] samples = Array.Empty<GrassSample>();

	List<Matrix4x4>[] matrices;
	readonly Matrix4x4[] batch = new Matrix4x4[MaxBatchSize];

	void OnEnable() {
		Rebuild();

		RenderPipelineManager.beginCameraRendering += OnBeginCameraRendering;
		Camera.onPreCull += OnCameraPreCull;
	}

	void OnDisable() {
		RenderPipelineManager.beginCameraRendering -= OnBeginCameraRendering;
		Camera.onPreCull -= OnCameraPreCull;
	}

	void OnBeginCameraRendering(
		ScriptableRenderContext context,
		Camera camera) {
		Draw(camera);
	}

	void OnCameraPreCull(Camera camera) {
		// Built-in render pipeline fallback.
		if (GraphicsSettings.currentRenderPipeline == null)
			Draw(camera);
	}

	void OnValidate() {
		overallDensity = Mathf.Max(0.001f, overallDensity);
		poissonAttempts = Mathf.Max(1, poissonAttempts);
		maximumTilt = Mathf.Max(0f, maximumTilt);

		if (isActiveAndEnabled)
			Rebuild();
	}

	public void Rebuild() {
		CollectSources();

		if (sources.Length == 0) {
			Clear();
			return;
		}

		Bounds bounds = GetLocalPlaneBounds();

		Vector3 planeScale = transform.lossyScale;

		float scaleX = Mathf.Abs(planeScale.x);
		float scaleY = Mathf.Abs(planeScale.y);
		float scaleZ = Mathf.Abs(planeScale.z);

		Vector2 scatterArea = new Vector2(
			bounds.size.x * scaleX,
			bounds.size.z * scaleZ
		);

		List<Vector2> points = GeneratePoissonPoints(
			scatterArea,
			PoissonRadius(overallDensity),
			poissonAttempts,
			seed
		);

		var random = new System.Random(seed);
		var generated = new GrassSample[points.Count];

		for (int i = 0; i < points.Count; i++) {
			Vector2 point = points[i];

			float yaw = Mathf.Lerp(
				yawRange.x,
				yawRange.y,
				(float)random.NextDouble()
			);

			float tiltX = Mathf.Lerp(
				-maximumTilt,
				maximumTilt,
				(float)random.NextDouble()
			);

			float tiltZ = Mathf.Lerp(
				-maximumTilt,
				maximumTilt,
				(float)random.NextDouble()
			);

			int sourceIndex = random.Next(sources.Length);

			Vector3 scaledPlanePosition = new Vector3(
				bounds.min.x * scaleX + point.x,
				bounds.max.y * scaleY,
				bounds.min.z * scaleZ + point.y
			);

			generated[i] = new GrassSample {
				position =
					transform.position +
					transform.rotation * scaledPlanePosition,

				rotation =
					transform.rotation *
					Quaternion.Euler(tiltX, yaw, tiltZ) *
					sources[sourceIndex].rotation,

				sourceIndex = sourceIndex,
				densityValue = (float)random.NextDouble()
			};
		}

		samples = generated;
		generatedInstances = samples.Length;

		matrices = new List<Matrix4x4>[sources.Length];

		for (int i = 0; i < matrices.Length; i++)
			matrices[i] = new List<Matrix4x4>();
	}

	public void Clear() {
		sources = Array.Empty<GrassSource>();
		samples = Array.Empty<GrassSample>();
		matrices = null;

		generatedInstances = 0;
		renderedInstances = 0;
		renderedVertexCount = 0;
	}

	void Draw(Camera renderingCamera) {
		if (!drawGrass || samples.Length == 0 || sources.Length == 0) {
			renderedInstances = 0;
			renderedVertexCount = 0;
			return;
		}

		Camera densityReference = densityCamera
		? densityCamera
		: renderingCamera;

		for (int i = 0; i < matrices.Length; i++)
			matrices[i].Clear();

		renderedInstances = 0;
		renderedVertexCount = 0;

		for (int i = 0; i < samples.Length; i++) {
			GrassSample sample = samples[i];

			float distance = densityReference
				? Vector3.Distance(
					densityReference.transform.position,
					sample.position)
				: 0f;

			float densityMultiplier =
				1f / (1f + distance * distanceFalloff);

			if (sample.densityValue > densityMultiplier)
				continue;

			GrassSource source = sources[sample.sourceIndex];

			matrices[sample.sourceIndex].Add(
				Matrix4x4.TRS(
					sample.position,
					sample.rotation,
					source.scale
				)
			);

			renderedInstances++;
			renderedVertexCount += source.mesh.vertexCount;
		}

		for (int sourceIndex = 0; sourceIndex < sources.Length; sourceIndex++) {
			GrassSource source = sources[sourceIndex];
			List<Matrix4x4> sourceMatrices = matrices[sourceIndex];

			int subMeshCount = Mathf.Min(
				source.mesh.subMeshCount,
				source.materials.Length
			);

			for (int start = 0; start < sourceMatrices.Count; start += MaxBatchSize) {
				int count = Mathf.Min(
					MaxBatchSize,
					sourceMatrices.Count - start
				);

				sourceMatrices.CopyTo(start, batch, 0, count);

				for (int subMesh = 0; subMesh < subMeshCount; subMesh++) {
					Material material = source.materials[subMesh];

					if (!material)
						continue;

					material.enableInstancing = true;

					Graphics.DrawMeshInstanced(
						source.mesh,
						subMesh,
						material,
						batch,
						count,
						null,
						castShadows
							? ShadowCastingMode.On
							: ShadowCastingMode.Off,
						receiveShadows,
						gameObject.layer,
						renderingCamera,
						LightProbeUsage.Off
					);
				}
			}
		}
	}

	void CollectSources() {
		if (!grassObjectGroup) {
			sources = Array.Empty<GrassSource>();
			return;
		}

		MeshFilter[] filters =
			grassObjectGroup.GetComponentsInChildren<MeshFilter>(true);

		var found = new List<GrassSource>();

		foreach (MeshFilter filter in filters) {
			if (!filter.sharedMesh)
				continue;

			MeshRenderer renderer = filter.GetComponent<MeshRenderer>();

			if (!renderer || renderer.sharedMaterials.Length == 0)
				continue;

			found.Add(new GrassSource {
				mesh = filter.sharedMesh,
				materials = renderer.sharedMaterials,
				scale = filter.transform.localScale,
				rotation = filter.transform.localRotation
			});
		}

		sources = found.ToArray();
	}

	Bounds GetLocalPlaneBounds() {
		MeshFilter filter = GetComponent<MeshFilter>();

		if (filter && filter.sharedMesh)
			return filter.sharedMesh.bounds;

		return new Bounds(Vector3.zero, new Vector3(10f, 0f, 10f));
	}

	static float PoissonRadius(float density) {
		/*
		 * Approximate conversion from desired instances per square unit
		 * to minimum Poisson separation.
		 */
		return 0.65f / Mathf.Sqrt(Mathf.Max(0.001f, density));
	}

	static List<Vector2> GeneratePoissonPoints(
		Vector2 area,
		float radius,
		int attempts,
		int seed) {
		var random = new System.Random(seed);
		float cellSize = radius / Mathf.Sqrt(2f);

		int gridWidth = Mathf.Max(1, Mathf.CeilToInt(area.x / cellSize));
		int gridHeight = Mathf.Max(1, Mathf.CeilToInt(area.y / cellSize));

		int[] grid = new int[gridWidth * gridHeight];

		for (int i = 0; i < grid.Length; i++)
			grid[i] = -1;

		var points = new List<Vector2>();
		var active = new List<int>();

		Vector2 first = new Vector2(
			(float)random.NextDouble() * area.x,
			(float)random.NextDouble() * area.y
		);

		points.Add(first);
		active.Add(0);
		SetGrid(first, 0);

		while (active.Count > 0) {
			int activeListIndex = random.Next(active.Count);
			int pointIndex = active[activeListIndex];
			Vector2 center = points[pointIndex];

			bool accepted = false;

			for (int attempt = 0; attempt < attempts; attempt++) {
				float angle =
					(float)random.NextDouble() * Mathf.PI * 2f;

				float distance =
					radius * (1f + (float)random.NextDouble());

				Vector2 candidate = center + new Vector2(
					Mathf.Cos(angle),
					Mathf.Sin(angle)
				) * distance;

				if (candidate.x < 0f ||
					candidate.y < 0f ||
					candidate.x >= area.x ||
					candidate.y >= area.y) {
					continue;
				}

				if (!IsValid(candidate))
					continue;

				int newIndex = points.Count;

				points.Add(candidate);
				active.Add(newIndex);
				SetGrid(candidate, newIndex);

				accepted = true;
				break;
			}

			if (!accepted)
				active.RemoveAt(activeListIndex);
		}

		return points;

		void SetGrid(Vector2 point, int pointIndex) {
			int x = Mathf.Clamp(
				Mathf.FloorToInt(point.x / cellSize),
				0,
				gridWidth - 1
			);

			int y = Mathf.Clamp(
				Mathf.FloorToInt(point.y / cellSize),
				0,
				gridHeight - 1
			);

			grid[x + y * gridWidth] = pointIndex;
		}

		bool IsValid(Vector2 candidate) {
			int cellX = Mathf.FloorToInt(candidate.x / cellSize);
			int cellY = Mathf.FloorToInt(candidate.y / cellSize);

			int minX = Mathf.Max(0, cellX - 2);
			int maxX = Mathf.Min(gridWidth - 1, cellX + 2);
			int minY = Mathf.Max(0, cellY - 2);
			int maxY = Mathf.Min(gridHeight - 1, cellY + 2);

			float radiusSquared = radius * radius;

			for (int y = minY; y <= maxY; y++) {
				for (int x = minX; x <= maxX; x++) {
					int nearbyIndex = grid[x + y * gridWidth];

					if (nearbyIndex < 0)
						continue;

					if ((candidate - points[nearbyIndex]).sqrMagnitude <
						radiusSquared) {
						return false;
					}
				}
			}

			return true;
		}
	}
}

#if UNITY_EDITOR
[CustomEditor(typeof(GrassScatterer))]
public class GrassScattererEditor : Editor {
	SerializedProperty generatedInstances;
	SerializedProperty renderedInstances;
	SerializedProperty renderedVertexCount;

	void OnEnable() {
		generatedInstances =
			serializedObject.FindProperty("generatedInstances");

		renderedInstances =
			serializedObject.FindProperty("renderedInstances");

		renderedVertexCount =
			serializedObject.FindProperty("renderedVertexCount");
	}

	public override void OnInspectorGUI() {
		serializedObject.Update();

		DrawPropertiesExcluding(
			serializedObject,
			"m_Script",
			"generatedInstances",
			"renderedInstances",
			"renderedVertexCount"
		);

		EditorGUILayout.Space();
		EditorGUILayout.LabelField("Statistics", EditorStyles.boldLabel);

		EditorGUILayout.LabelField(
			"Generated instances",
			generatedInstances.intValue.ToString("N0")
		);

		EditorGUILayout.LabelField(
			"Rendered instances",
			renderedInstances.intValue.ToString("N0")
		);

		EditorGUILayout.LabelField(
			"Rendered vertices",
			renderedVertexCount.longValue.ToString("N0")
		);

		EditorGUILayout.Space();

		if (GUILayout.Button("Rebuild Scatter")) {
			foreach (UnityEngine.Object targetObject in targets) {
				var scatterer = (GrassScatterer)targetObject;

				Undo.RecordObject(scatterer, "Rebuild Grass Scatter");
				scatterer.Rebuild();
				EditorUtility.SetDirty(scatterer);
			}
		}

		if (GUILayout.Button("Clear")) {
			foreach (UnityEngine.Object targetObject in targets) {
				var scatterer = (GrassScatterer)targetObject;

				Undo.RecordObject(scatterer, "Clear Grass Scatter");
				scatterer.Clear();
				EditorUtility.SetDirty(scatterer);
			}
		}

		serializedObject.ApplyModifiedProperties();

		if (!Application.isPlaying)
			SceneView.RepaintAll();
	}
}
#endif