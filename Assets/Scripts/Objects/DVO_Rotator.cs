using UnityEngine;

public class DVO_Rotator : DVObject {
	public Vector3 axes;

	public override void Init() {
		
	}

	public override void UpdateState(ulong time) {
		float t = (float)time / DVConfig.timeScale;
		transform.localRotation = Quaternion.Euler(
			axes.x * t,
			axes.y * t,
			axes.z * t
		);
	}
}