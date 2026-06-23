using UnityEngine;

public class PoseAnimObj : DVObject {
	public string AnimObjAssetPath; // fbx
	public float Scale;

	PoseCopy.PoseAnimation anim;

	Transform target;

	private void Awake() {
		target = SceneManager.Instance.Armature;

		PoseCopy.LoadFBX(AnimObjAssetPath, out var model, out var clip);

		anim = PoseCopy.GeneratePoseAnim(model, clip);

		anim.Scale(Scale);
	}

	public override void UpdateState(ulong time) {
		var pose = anim.Sample(time);

		PoseCopy.CopyPose(pose, target);
	}
}