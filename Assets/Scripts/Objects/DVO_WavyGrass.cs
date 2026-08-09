using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

[ExecuteAlways]
public class DVO_WavyGrass : DVObject {
	public bool wave;
	Material material;

	Material shared;
	LocalKeyword previewKW;
	
	public override void Init() {
		material = GetComponent<Renderer>().material;
	}
	
	public override void UpdateState(ulong time) {
		if (wave)
			material.SetFloat("_Phase", time / (float)DVConfig.timeScale);
	}

	private void OnEnable() {
		shared = GetComponent<Renderer>().sharedMaterial;
		previewKW = new LocalKeyword(shared.shader, "_PREVIEW_WAVE");
	}
	private void OnDisable() {
		shared = null;
	}

	void Update() {
		if (Application.isPlaying) return;
		if (!wave) return;
		shared.SetKeyword(previewKW, wave);
	}

	public override DVSMemory.BBox GenerateBBoxExact(Camera camera) {
		return new DVSMemory.BBox() { rendered = false };
	}
}