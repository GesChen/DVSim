using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public abstract class DVO_Vehicle : DVObject {
	// dynamically switch model based on distance to armature eg center of frame
	public DVO_VehicleLOD HiRes;
	public DVO_VehicleLOD LowRes;

	const float HiResDist = 10f;
	[HideInInspector] public bool UsingHiRes;

	public void UpdateModel() {
		Vector3 reference;
		if (DVManager.Instance.Playing)
			reference = DVManager.Instance.ArmatureInUse.transform.position;
		else reference = Vector3.zero;

		UsingHiRes = (transform.position - reference).sqrMagnitude < HiResDist;

		HiRes.gameObject.SetActive(UsingHiRes);
		LowRes.gameObject.SetActive(!UsingHiRes);
	}

	// dont override this
	public override void Init() {
		GenerateID();
		InitVehicle();
		HiRes.Init();
		LowRes.Init();

		Randomize();
	}

	protected abstract void InitVehicle();

	protected abstract void Randomize();

	public override DVSMemory.InterBBox GenerateBBoxExact(Camera camera) =>
		UsingHiRes ? HiRes.GenerateBBox(camera) : LowRes.GenerateBBox(camera);

}