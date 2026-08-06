using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;

public class DVO_Car : DVObject {
	public int paintMatIndex;

	Material material;

	public override void Init() {
		material = Renderer.materials[paintMatIndex];
	}

	public void SetColor(int col) {
		if (col < 0 || col > 7) Debug.LogError($"invalid color {col} must be 0-7");
		material.SetInt("_PaletteIndex", col);
	}

	public void TestColor() {
		material = Renderer.sharedMaterials[paintMatIndex];
		int col = Random.Range(0, 8);
		Debug.Log($"testing {col}");
		SetColor(col);
	}

	public override void UpdateState(ulong time) {
		
	}
}

[CustomEditor(typeof(DVO_Car))]
public class DVOCarEditor : Editor {
	public override void OnInspectorGUI() {
		DrawDefaultInspector();

		var comp = (DVO_Car)target;
		if (GUILayout.Button("Test color")) {
			comp.TestColor();
		}
	}
}
