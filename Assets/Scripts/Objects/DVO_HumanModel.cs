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

	private SkinnedMeshRenderer SMRenderer;
	Mesh bakedMesh;
	readonly List<Vector3> bmVerts = new();

	public override void Init() {
		SMRenderer = GetComponent<SkinnedMeshRenderer>();

		// check to see all model types are fulfilled
		foreach (var arm in DVManager.Instance.Armatures) {
			if (!Models.Any(m => m.TargetArmatureType == arm.Type)) {
				Debug.LogError($"Human model {name} lacks the model for armature type \"{arm.Type}\"");
			}
		}

		bakedMesh = new Mesh { name = "Vertex Picker Baked Mesh" };

		// reconstruct them all
		foreach (var m in Models) {
			m.Reconstruct();
		}
	}

	public override void UpdateState(ulong time) {
		
	}

	public void SetToCurArmature() {
		DVO_Armature armatureInUse = DVManager.Instance.ArmatureInUse;
		var root = armatureInUse.RootBoneTransform;
		SMRenderer.rootBone = root;

		ModelMapping targetModel = Models.Find(m => m.TargetArmatureType == armatureInUse.Type);
		var targetBoneStructure = targetModel.BoneStructure;
		var allSubBones = root.GetComponentsInChildren<Transform>();
		var reconstructed = targetBoneStructure.Select(name => allSubBones.First(b => b.name == name)).ToArray();

		SMRenderer.bones = reconstructed;

		// set mesh
		SMRenderer.sharedMesh = 
			targetModel.SourceAsset.GetComponentInChildren<SkinnedMeshRenderer>().sharedMesh;
	}

	// make this dynamic and per model later 
	// once needed
	static int[] boundsSMPLXLandmarkIndices = new[] {
		3133, 3066, 3214, 2563, 9104, 4357, 7486, 9300, 8372, 6816, 4866, 8563, 3850, 5481, 5570, 8090, 3977, 4501, 10394, 9440, 6899, 5299, 5143, 6036, 4139, 7772, 7256, 10284, 8406, 6788, 973, 3036, 5693, 4799, 4630, 5554, 7903, 4137, 9409, 6969, 9302, 4545, 3863, 8048
	};

	public override DVSMemory.InterBBox GenerateBBoxExact(Camera camera) {
		SMRenderer.BakeMesh(bakedMesh);
		bakedMesh.GetVertices(bmVerts);

		Vector2 min = Vector2.positiveInfinity;
		Vector2 max = Vector2.negativeInfinity;
		Vector3 total = Vector3.zero;

		foreach (int landmark in boundsSMPLXLandmarkIndices) {
			Vector3 v3 = transform.TransformPoint(bmVerts[landmark]); // use matrix if slow
			Vector2 v2 = camera.WorldToScreenPoint(v3);

			min = Vector2.Min(min, v2);
			max = Vector2.Max(max, v2);
			total += v3;
			//DebugExtra.DrawPoint(v3, duration: .2f);
		}
		Vector3 center = total / boundsSMPLXLandmarkIndices.Length;
		//DebugExtra.DrawRectSS(min, max, camera, drawGame: true, duration: .3f);
		//Debug.Log($"min {min} max {max}");

		return new() {
			min = min,
			max = max,
			dist = (camera.transform.position - center).magnitude,
		};
	}
}
