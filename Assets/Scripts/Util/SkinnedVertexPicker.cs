using System.Collections.Generic;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

[ExecuteAlways]
[RequireComponent(typeof(SkinnedMeshRenderer))]
public class SkinnedVertexPicker : MonoBehaviour {
	[SerializeField] int vertexIndex;
	[SerializeField] List<int> vertexIndices = new();

	[SerializeField] GameObject target;

	[SerializeField] float previewSize = 0.02f;
	[SerializeField] Color currentColor = Color.red;
	[SerializeField] Color serializedColor = Color.green;
	[SerializeField] Color closestColor = Color.yellow;

	SkinnedMeshRenderer smr;
	Mesh bakedMesh;

	public int VertexCount =>
		smr && smr.sharedMesh ? smr.sharedMesh.vertexCount : 0;

	void OnEnable() {
		smr = GetComponent<SkinnedMeshRenderer>();
		bakedMesh = new Mesh { name = "Vertex Picker Baked Mesh" };
	}

	void Update() {
		if (!smr || !smr.sharedMesh || VertexCount == 0)
			return;

		vertexIndex = Mathf.Clamp(vertexIndex, 0, VertexCount - 1);

		smr.BakeMesh(bakedMesh);
		Vector3[] vertices = bakedMesh.vertices;

		DrawVertex(vertices, vertexIndex, currentColor);

		foreach (int index in vertexIndices)
			if (index >= 0 && index < vertices.Length)
				DrawVertex(vertices, index, serializedColor);

		if (target)
			DrawVertex(vertices, GetClosestVertex(vertices), closestColor);
	}

	int GetClosestVertex(Vector3[] vertices) {
		Vector3 targetPosition = target.transform.position;
		int closestIndex = 0;
		float closestDistance = float.PositiveInfinity;

		for (int i = 0; i < vertices.Length; i++) {
			Vector3 worldPosition = smr.transform.TransformPoint(vertices[i]);
			float distance = (worldPosition - targetPosition).sqrMagnitude;

			if (distance >= closestDistance)
				continue;

			closestDistance = distance;
			closestIndex = i;
		}

		return closestIndex;
	}

	void DrawVertex(Vector3[] vertices, int index, Color color) {
		DebugExtra.DrawEmpty(
			smr.transform.TransformPoint(vertices[index]),
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
	}

#if UNITY_EDITOR
	[CustomEditor(typeof(SkinnedVertexPicker))]
	class SkinnedVertexPickerEditor : Editor {
		public override void OnInspectorGUI() {
			serializedObject.Update();

			var picker = (SkinnedVertexPicker)target;
			var index = serializedObject.FindProperty("vertexIndex");
			var indices = serializedObject.FindProperty("vertexIndices");

			int max = Mathf.Max(0, picker.VertexCount - 1);

			EditorGUILayout.LabelField(
				"Vertex Count",
				picker.VertexCount.ToString()
			);

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

			index.intValue = Mathf.Clamp(index.intValue, 0, max);

			EditorGUILayout.Space();

			using (new EditorGUILayout.HorizontalScope()) {
				if (GUILayout.Button("Add"))
					AddIndex(indices, index.intValue);

				using (new EditorGUI.DisabledScope(
					!picker.target ||
					!picker.smr ||
					!picker.smr.sharedMesh)) {
					if (GUILayout.Button("Add Closest")) {
						picker.smr.BakeMesh(picker.bakedMesh);
						AddIndex(
							indices,
							picker.GetClosestVertex(picker.bakedMesh.vertices)
						);
					}
				}

				if (GUILayout.Button("Clear"))
					indices.ClearArray();
			}

			if (GUILayout.Button("Copy Serialized To Clipboard")) {
				var values = new int[indices.arraySize];

				for (int i = 0; i < values.Length; i++)
					values[i] = indices
						.GetArrayElementAtIndex(i)
						.intValue;

				EditorGUIUtility.systemCopyBuffer = values.ToBetterString();
			}

			EditorGUILayout.PropertyField(indices);
			EditorGUILayout.PropertyField(
				serializedObject.FindProperty("target")
			);
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

		static void AddIndex(SerializedProperty indices, int value) {
			int position = indices.arraySize;
			indices.InsertArrayElementAtIndex(position);
			indices.GetArrayElementAtIndex(position).intValue = value;
		}
	}
#endif
}