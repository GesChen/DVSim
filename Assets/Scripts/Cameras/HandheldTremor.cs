using UnityEngine;

public class HandheldTremor : MonoBehaviour {
	DVS MainSensor;

	[Header("Amplitude (degrees)")]
	public float Scale = 1;
	public Vector3 Amplitude = new(0.15f, 0.12f, 0.08f);

	[Header("Base Frequency (Hz)")]
	public Vector3 Frequency = new(8.0f, 9.0f, 7.0f);

	[Header("fBm")]
	[Range(1, 8)]
	public int Octaves = 3;

	public Vector3 Lacunarity = new(2.0f, 2.0f, 2.0f);
	public Vector3 Gain = new(0.5f, 0.5f, 0.5f);

	[Header("Time Scale")]
	public Vector3 TimeScale = Vector3.one;

	private Vector3 _seed0;
	private Vector3 _seed1;

	Quaternion baseRot;

	private void Awake() {
		MainSensor = GetComponent<DVS>();
		MainSensor.OnInit += Init;
		MainSensor.OnTick += UpdateTremor;
	}

	void Init() {
		baseRot = transform.localRotation;
	}

	public void UpdateTremor(double time) {
		if (!enabled) return;

		float t = (float)time;

		Vector3 euler = new Vector3(
			Fbm(_seed0.x, _seed1.x, t * Frequency.x * TimeScale.x, Octaves, Lacunarity.x, Gain.x) * Amplitude.x,
			Fbm(_seed0.y, _seed1.y, t * Frequency.y * TimeScale.y, Octaves, Lacunarity.y, Gain.y) * Amplitude.y,
			Fbm(_seed0.z, _seed1.z, t * Frequency.z * TimeScale.z, Octaves, Lacunarity.z, Gain.z) * Amplitude.z
		) * Scale;

		transform.localRotation = baseRot * Quaternion.Euler(euler);
	}

	static float Fbm(
		float seedX,
		float seedY,
		float time,
		int octaves,
		float lacunarity,
		float gain) {
		float value = 0f;
		float amplitude = 1f;
		float frequency = 1f;
		float normalization = 0f;

		for (int i = 0; i < octaves; i++) {
			float n = Mathf.PerlinNoise(
				seedX + time * frequency,
				seedY) * 2f - 1f;

			value += n * amplitude;
			normalization += amplitude;

			frequency *= lacunarity;
			amplitude *= gain;
		}

		return value / normalization;
	}
}