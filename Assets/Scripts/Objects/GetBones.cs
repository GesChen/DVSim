using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class GetBones : MonoBehaviour {
	public Transform hips;
	public Transform replacementHips;

	public void PrintBones() {
		var smr = GetComponent<SkinnedMeshRenderer>();

		Debug.Log("SMR bones:\n" +
			string.Join(", ", smr.bones.Select(b => b.name)));

		Debug.Log("Armature bones:\n" +
			string.Join(", ", hips.GetComponentsInChildren<Transform>(true)
				.Select(t => t.name)));
	}

	public void TestRemap() {
		var smr = GetComponent<SkinnedMeshRenderer>();

		if (replacementHips == null) {
			Debug.LogError("Assign Replacement Hips.");
			return;
		}

		// Test implementation assumes bone names are unique.
		var replacementBones =
			replacementHips
				.GetComponentsInChildren<Transform>(true)
				.ToDictionary(t => t.name);

		var oldBones = smr.bones;
		var newBones = new Transform[oldBones.Length];

		for (int i = 0; i < oldBones.Length; i++) {
			Transform oldBone = oldBones[i];

			if (!replacementBones.TryGetValue(oldBone.name, out Transform newBone)) {
				Debug.LogError($"Missing replacement bone: {oldBone.name}");
				return;
			}

			newBones[i] = newBone;

			Debug.Log(
				$"[{i}] {oldBone.name}: " +
				$"{GetPath(oldBone)} -> {GetPath(newBone)}"
			);
		}

		smr.bones = newBones;

		// Remap rootBone as well.
		if (smr.rootBone != null &&
			replacementBones.TryGetValue(smr.rootBone.name, out Transform newRoot)) {
			smr.rootBone = newRoot;
		}

		Debug.Log($"Remapped {newBones.Length} bones.");
	}

	private static string GetPath(Transform t) {
		var names = new List<string>();

		while (t != null) {
			names.Add(t.name);
			t = t.parent;
		}

		names.Reverse();
		return string.Join("/", names);
	}
}

#if UNITY_EDITOR

[UnityEditor.CustomEditor(typeof(GetBones))]
public class GetBonesEditor : UnityEditor.Editor {
	public override void OnInspectorGUI() {
		DrawDefaultInspector();

		var getBones = (GetBones)target;

		GUILayout.Space(10);

		if (GUILayout.Button("Print Bones"))
			getBones.PrintBones();

		if (GUILayout.Button("Test Remap"))
			getBones.TestRemap();
	}
}

#endif