using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class DVO_Armature : DVObject {
	public string Type;
	public Transform RootBoneTransform;
	public Vector3 groundingOffset;

	public override void Init() {
	}

	public override void UpdateState(ulong time) {
		
	}

	public void ApplyPose(Poses.Pose pose) {
		Poses.CopyPose(pose, transform);
	}
}