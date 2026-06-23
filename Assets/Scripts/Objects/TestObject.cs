using UnityEngine;

public class TestObject : DVObject {
	public float speed;
	public Vector3 off;
	public Vector3 pos;
	public Vector3 rot;

	Vector3 posInit;

	private void Awake() {
		posInit = transform.position;
	}

	public override void UpdateState(ulong time) {
		float t = time;
		t /= DVConfig.TimeScale;
		t *= speed;

		transform.position = posInit + 
			new Vector3(
				Mathf.Sin(t + off.x) * pos.x,
				Mathf.Sin(t + off.y) * pos.y,
				Mathf.Sin(t + off.z) * pos.z);

		transform.rotation = Quaternion.Euler(rot.x * t, rot.y * t, rot.z * t);
	}
}