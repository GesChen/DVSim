using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;

public class DVO_Car : DVO_Vehicle {
	public Transform frontWheels;
	public Transform backWheels;

	protected override void InitVehicle() {
		
	}

	protected override void Randomize() {
		bool hasHiPart = HiRes.TryGetComponent(out DVO_CarPart hiResPart);
		bool hasLowPart = LowRes.TryGetComponent(out DVO_CarPart lowResPart);

		if (!(hasHiPart && hasLowPart)) {
			Debug.LogError("Both parts of DVO Car need to be carpart");
		}

		int col = (int)(ID % 7);
		hiResPart.SetColor(col);
		lowResPart.SetColor(col);
	}

	public override void UpdateState(ulong time) {
		
	}
}