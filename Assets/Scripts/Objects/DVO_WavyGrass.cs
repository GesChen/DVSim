using System.Collections;
using System.Collections.Generic;
using UnityEngine;

[ExecuteAlways]
public class DVO_WavyGrass : DVObject {
	public bool wave;
	Material material;
	Material shared;
	
	public override void Init() {
		material = GetComponent<Renderer>().material;
	}
	
	public override void UpdateState(ulong time) {
		if (wave)
			material.SetFloat("_Phase", time / (float)DVConfig.timeScale);
	}

	private void OnEnable() {
		shared = GetComponent<Renderer>().sharedMaterial;
	}
	private void OnDisable() {
		shared = null;
	}

	void Update() {
		if (Application.isPlaying) return;
		if (!wave) return;
		shared.SetFloat("_Phase", Time.timeSinceLevelLoad);
	}

	public override DVSMemory.BBox GenerateBBoxExact(Camera camera) {
		return new DVSMemory.BBox() { rendered = false };
	}
}