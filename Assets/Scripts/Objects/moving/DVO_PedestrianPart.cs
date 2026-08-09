using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_PedestrianPart : MonoBehaviour {
	Material material;

	public void Init() {
		if (Application.isPlaying)
			material = GetComponent<Renderer>().material;
	}

	public void Randomize(uint srcID) {
		int selection = (int)(srcID % DVO_Pedestrian.SMPLitexTextures.Length);

		if (Application.isPlaying)
			material.SetTexture("_BaseMap", DVO_Pedestrian.SMPLitexTextures[selection]);
	}

	public void UpdateState(ulong t) {

	}
}