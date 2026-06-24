using UnityEngine;

public class DVO_HumanModel : DVObject {
	private SkinnedMeshRenderer SkinnedMeshRenderer;
	public override void Init() {
		SkinnedMeshRenderer = GetComponent<SkinnedMeshRenderer>();
		SkinnedMeshRenderer.rootBone = SceneManager.Instance.Armature.Find("Hips");
	}

	public override void UpdateState(ulong time) {
		
	}
}
