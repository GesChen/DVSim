using UnityEngine;

public class DVO_Environment : DVObject {
	public DVO_Lighting lighting;

	public override void UpdateState(ulong time) {
	}
	public override void Init() {
		if (lighting != null) SceneManager.Instance.LoadLighting(lighting);
		else Debug.LogWarning($"Environment {gameObject.name} has not set a target lighting, using the last loaded one");
	}
}
