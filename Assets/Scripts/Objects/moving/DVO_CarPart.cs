using System.Collections;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

public class DVO_CarPart : MonoBehaviour {
	public int paintMatIndex;

	Material material;
	public void SetColor(int col) {
		if (col < 0 || col > 7) Debug.LogError($"invalid color {col} must be 0-7");
		if (material == null) {
			if (Application.isPlaying)
				material = GetComponent<Renderer>().materials[paintMatIndex];
			else return; // dont use shared material, this will just break shit
			// rather just dont randomize colors in editor 
		}
		material.SetInt("_PaletteIndex", col);
	}

	public void TestColor() {
		material = GetComponent<Renderer>().sharedMaterials[paintMatIndex];
		int col = Random.Range(0, 8);
		Debug.Log($"testing {col}");
		SetColor(col);
	}
}



[CustomEditor(typeof(DVO_CarPart))]
public class DVOCarEditor : Editor {
	public override void OnInspectorGUI() {
		DrawDefaultInspector();

		var comp = (DVO_CarPart)target;
		if (GUILayout.Button("Test color")) {
			comp.TestColor();
		}
	}
}
