using System.Linq;
using UnityEngine;

public class DVO_HumanModel : DVObject {
	public GameObject SourceAsset;
	static string[] BoneStructure;

	private SkinnedMeshRenderer SkinnedMeshRenderer;

	public override void Init() {
		SkinnedMeshRenderer = GetComponent<SkinnedMeshRenderer>();

		var hips = SceneManager.Instance.Armature.Find("Hips");
		SkinnedMeshRenderer.rootBone = hips;

		// reconstruct bone structure
		if (BoneStructure == null) {
			var srcObj = Instantiate(SourceAsset);
			var srcSMR = srcObj.GetComponentInChildren<SkinnedMeshRenderer>();

			BoneStructure = srcSMR.bones.Select(b => b.name).ToArray();

			DestroyImmediate(srcObj);
		}

		var allSubBones = hips.GetComponentsInChildren<Transform>();
		var reconstructed = BoneStructure.Select(name => allSubBones.First(b => b.name == name)).ToArray();

		SkinnedMeshRenderer.bones = reconstructed;
	}

	public override void UpdateState(ulong time) {
		
	}
}
