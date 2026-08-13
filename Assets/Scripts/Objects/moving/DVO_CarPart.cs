using System.Collections;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

public class DVO_CarPart : DVO_VehicleLOD {
	public int paintMatIndex;

	public void SetColor(int col) {
		if (col < 0 || col > 7) Debug.LogError($"invalid color {col} must be 0-7");
		if (!Application.isPlaying) return;
		material.SetInt("_PaletteIndex", col);
	}

	public void TestColor() {
		material = GetComponent<Renderer>().sharedMaterials[paintMatIndex];
		int col = Random.Range(0, 8);
		Debug.Log($"testing {col}");
		SetColor(col);
	}
}