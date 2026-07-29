using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_WavyGrass : DVObject {
	Material material;
	public override void Init() {
		material = GetComponent<Renderer>().material;
	}
	public override void UpdateState(ulong time) {
		material.SetFloat("_Phase", time / (float)DVConfig.timeScale);
	}
	public override DVSMemory.BBox GenerateBBoxExact(Camera camera) {
		return new DVSMemory.BBox() { rendered = false };
	}
}