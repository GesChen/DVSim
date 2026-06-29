using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class DVO_ConstTransform : DVObject {
	public Vector3 constPositionRate;
	public Vector3 sinPositionAmount;
	public Vector3 sinPositionRate;


	Vector3 initialPosition;

	public override void Init() {
		initialPosition = transform.position;
	}

	public override void UpdateState(ulong time) {
		float t = (float)time / DVConfig.TimeScale;

		transform.position = initialPosition
			+ constPositionRate * t
			+ new Vector3(
				sinPositionAmount.x * Mathf.Sin(sinPositionRate.x * t),
				sinPositionAmount.y * Mathf.Sin(sinPositionRate.y * t),
				sinPositionAmount.z * Mathf.Sin(sinPositionRate.z * t));
	}
}