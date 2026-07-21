using UnityEngine;

[ExecuteAlways]
public class PreviewCamera : MonoBehaviour {
	public Camera Target;

	Camera cam;
	private void Awake() {
		cam = GetComponent<Camera>();
	}

	private void Update() {
		cam.CopyFrom(Target);
		cam.targetTexture = null;
		transform.SetPositionAndRotation(Target.transform.position, Target.transform.rotation);
	}
}