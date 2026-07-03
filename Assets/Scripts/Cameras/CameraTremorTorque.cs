using UnityEngine;

public class CameraTremorTorque : MonoBehaviour {
	[SerializeField] private Rigidbody rb;

	[Header("Tremor")]
	[SerializeField] private float tremorStrength = 0.02f;
	[SerializeField] private float tremorFrequency = 9.0f;

	[Header("Per-axis scale")]
	[SerializeField] private Vector3 axisScale = new Vector3(1.0f, 0.7f, 0.4f);

	private float seedX;
	private float seedY;
	private float seedZ;

	private void Awake() {
		if (!rb)
			rb = GetComponent<Rigidbody>();

		seedX = Random.value * 1000f;
		seedY = Random.value * 1000f;
		seedZ = Random.value * 1000f;
	}

	private void FixedUpdate() {
		float t = Time.fixedTime * tremorFrequency;

		Vector3 noise = new Vector3(
			Mathf.PerlinNoise(seedX, t) * 2f - 1f,
			Mathf.PerlinNoise(seedY, t) * 2f - 1f,
			Mathf.PerlinNoise(seedZ, t) * 2f - 1f
		);

		Vector3 localTorque = Vector3.Scale(noise, axisScale) * tremorStrength;

		rb.AddRelativeTorque(localTorque, ForceMode.Acceleration);
	}
}