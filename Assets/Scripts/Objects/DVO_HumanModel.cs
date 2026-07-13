using System.Linq;
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_HumanModel : DVObject {
	[Serializable]
	public class ModelMapping {
		public string TargetArmatureType;
		public GameObject SourceAsset;
		public string[] BoneStructure;

		public void Reconstruct() {
			var srcObj = Instantiate(SourceAsset);
			var srcSMR = srcObj.GetComponentInChildren<SkinnedMeshRenderer>();

			BoneStructure = srcSMR.bones.Select(b => b.name).ToArray();

			DestroyImmediate(srcObj);
		}
	}
	public List<ModelMapping> Models;

	private SkinnedMeshRenderer SkinnedMeshRenderer;

	public override void Init() {
		SkinnedMeshRenderer = GetComponent<SkinnedMeshRenderer>();

		// check to see all model types are fulfilled
		foreach (var arm in SceneManager.Instance.Armatures) {
			if (!Models.Any(m => m.TargetArmatureType == arm.Type)) {
				Debug.LogError($"Human model {name} lacks the model for armature type \"{arm.Type}\"");
			}
		}

		// reconstruct them all
		foreach (var m in Models) {
			m.Reconstruct();
		}
	}

	public override void UpdateState(ulong time) {
		
	}

	public void SetToCurArmature() {
		DVO_Armature armatureInUse = SceneManager.Instance.ArmatureInUse;
		var root = armatureInUse.RootBoneTransform;
		SkinnedMeshRenderer.rootBone = root;

		ModelMapping targetModel = Models.Find(m => m.TargetArmatureType == armatureInUse.Type);
		var targetBoneStructure = targetModel.BoneStructure;
		var allSubBones = root.GetComponentsInChildren<Transform>();
		var reconstructed = targetBoneStructure.Select(name => allSubBones.First(b => b.name == name)).ToArray();

		SkinnedMeshRenderer.bones = reconstructed;

		// set mesh
		SkinnedMeshRenderer.sharedMesh = 
			targetModel.SourceAsset.GetComponentInChildren<SkinnedMeshRenderer>().sharedMesh;
	}
}
