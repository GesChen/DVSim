using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public abstract class DVO_Vehicle : DVObject {

	// dynamically switch model based on distance to armature eg center of frame
	public GameObject HiRes;
	public GameObject LowRes;

	const float HiResDist = 10f;

	public void UpdateModel() {
		Vector3 reference;
		if (DVManager.Instance.Playing)
			reference = SceneManager.Instance.ArmatureInUse.transform.position;
		else reference = Vector3.zero;

			bool useHiRes = (transform.position - reference).sqrMagnitude < HiResDist;

		HiRes.SetActive(useHiRes);
		LowRes.SetActive(!useHiRes);
	}

	public override void Init() {
		Randomize();
	}

	protected abstract void Randomize();
}