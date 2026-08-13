using System.Collections.Generic;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

[ExecuteAlways]
public class VertexPicker : MonoBehaviour {
	[SerializeField] int vertexIndex;
	[SerializeField] List<int> vertexIndices = new();

	[SerializeField] GameObject target;

	[SerializeField] float previewSize = 0.02f;
	[SerializeField] Color currentColor = Color.red;
	[SerializeField] Color serializedColor = Color.green;
	[SerializeField] Color closestColor = Color.yellow;

	MeshFilter meshFilter;
	SkinnedMeshRenderer skinnedMeshRenderer;
	Mesh bakedMesh;

	Mesh SourceMesh {
		get {
			if (meshFilter && meshFilter.sharedMesh)
				return meshFilter.sharedMesh;

			if (skinnedMeshRenderer && skinnedMeshRenderer.sharedMesh)
				return skinnedMeshRenderer.sharedMesh;

			return null;
		}
	}

	Transform MeshTransform {
		get {
			if (meshFilter && meshFilter.sharedMesh)
				return meshFilter.transform;

			if (skinnedMeshRenderer && skinnedMeshRenderer.sharedMesh)
				return skinnedMeshRenderer.transform;

			return transform;
		}
	}

	public int VertexCount =>
		SourceMesh ? SourceMesh.vertexCount : 0;

	void OnEnable() {
		RefreshComponents();

		bakedMesh = new Mesh {
			name = "Vertex Picker Baked Mesh"
		};
	}

	void OnValidate() {
		RefreshComponents();
	}

	void RefreshComponents() {
		meshFilter = GetComponent<MeshFilter>();
		skinnedMeshRenderer = GetComponent<SkinnedMeshRenderer>();
	}

	void Update() {
		if (!TryGetVertices(out Vector3[] vertices))
			return;

		vertexIndex = Mathf.Clamp(vertexIndex, 0, vertices.Length - 1);

		DrawVertex(vertices, vertexIndex, currentColor);

		foreach (int index in vertexIndices) {
			if (index >= 0 && index < vertices.Length)
				DrawVertex(vertices, index, serializedColor);
		}

		if (target)
			DrawVertex(vertices, GetClosestVertex(vertices), closestColor);
	}

	bool TryGetVertices(out Vector3[] vertices) {
		vertices = null;

		// Prefer a normal MeshFilter.
		if (meshFilter && meshFilter.sharedMesh) {
			vertices = meshFilter.sharedMesh.vertices;
			return vertices.Length > 0;
		}

		// Fall back to the deformed SkinnedMeshRenderer mesh.
		if (
			skinnedMeshRenderer &&
			skinnedMeshRenderer.sharedMesh &&
			bakedMesh
		) {
			skinnedMeshRenderer.BakeMesh(bakedMesh);
			vertices = bakedMesh.vertices;
			return vertices.Length > 0;
		}

		return false;
	}

	public int GetClosestVertex() {
		if (!target || !TryGetVertices(out Vector3[] vertices))
			return -1;

		return GetClosestVertex(vertices);
	}

	int GetClosestVertex(Vector3[] vertices) {
		Vector3 targetPosition = target.transform.position;
		Transform meshTransform = MeshTransform;

		int closestIndex = 0;
		float closestDistance = float.PositiveInfinity;

		for (int i = 0; i < vertices.Length; i++) {
			Vector3 worldPosition =
				skinnedMeshRenderer ? vertices[i] : MeshTransform.TransformPoint(vertices[i]);

			float distance =
				(worldPosition - targetPosition).sqrMagnitude;

			if (distance >= closestDistance)
				continue;

			closestDistance = distance;
			closestIndex = i;
		}

		return closestIndex;
	}

	void DrawVertex(Vector3[] vertices, int index, Color color) {
		DebugExtra.DrawEmpty(
			skinnedMeshRenderer ? vertices[index] : MeshTransform.TransformPoint(vertices[index]),
			previewSize,
			color
		);
	}

	void OnDisable() {
		if (!bakedMesh)
			return;

		if (Application.isPlaying)
			Destroy(bakedMesh);
		else
			DestroyImmediate(bakedMesh);

		bakedMesh = null;
	}
}

#if UNITY_EDITOR
[CustomEditor(typeof(VertexPicker))]
class VertexPickerEditor : Editor {
	public override void OnInspectorGUI() {
		serializedObject.Update();

		var picker = (VertexPicker)target;

		var index =
			serializedObject.FindProperty("vertexIndex");

		var indices =
			serializedObject.FindProperty("vertexIndices");

		var targetProperty =
			serializedObject.FindProperty("target");

		int max = Mathf.Max(0, picker.VertexCount - 1);

		EditorGUILayout.LabelField(
			"Vertex Count",
			picker.VertexCount.ToString()
		);

		using (new EditorGUI.DisabledScope(picker.VertexCount == 0)) {
			using (new EditorGUILayout.HorizontalScope()) {
				if (GUILayout.Button("-", GUILayout.Width(30)))
					index.intValue--;

				index.intValue = EditorGUILayout.IntSlider(
					"Vertex",
					index.intValue,
					0,
					max
				);

				if (GUILayout.Button("+", GUILayout.Width(30)))
					index.intValue++;
			}

			index.intValue =
				Mathf.Clamp(index.intValue, 0, max);

			EditorGUILayout.Space();

			using (new EditorGUILayout.HorizontalScope()) {
				if (GUILayout.Button("Add"))
					AddIndex(indices, index.intValue);

				using (new EditorGUI.DisabledScope(
					targetProperty.objectReferenceValue == null)) {

					if (GUILayout.Button("Add Closest")) {
						int closest = picker.GetClosestVertex();

						if (closest >= 0)
							AddIndex(indices, closest);
					}
				}

				if (GUILayout.Button("Clear"))
					indices.ClearArray();
			}
		}

		if (GUILayout.Button("Copy Serialized To Clipboard")) {
			var values = new int[indices.arraySize];

			for (int i = 0; i < values.Length; i++) {
				values[i] = indices
					.GetArrayElementAtIndex(i)
					.intValue;
			}

			EditorGUIUtility.systemCopyBuffer =
				values.ToBetterString();
		}

		EditorGUILayout.PropertyField(indices);
		EditorGUILayout.PropertyField(targetProperty);

		EditorGUILayout.PropertyField(
			serializedObject.FindProperty("previewSize")
		);

		EditorGUILayout.PropertyField(
			serializedObject.FindProperty("currentColor")
		);

		EditorGUILayout.PropertyField(
			serializedObject.FindProperty("serializedColor")
		);

		EditorGUILayout.PropertyField(
			serializedObject.FindProperty("closestColor")
		);

		serializedObject.ApplyModifiedProperties();

		if (GUI.changed) {
			EditorUtility.SetDirty(target);
			SceneView.RepaintAll();
		}
	}

	static void AddIndex(
		SerializedProperty indices,
		int value
	) {
		int position = indices.arraySize;

		indices.InsertArrayElementAtIndex(position);

		indices
			.GetArrayElementAtIndex(position)
			.intValue = value;
	}
}
#endif