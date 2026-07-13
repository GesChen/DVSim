using UnityEngine;

public class DVO_PoseAnim : DVObject {
	public string AnimObjAssetPath; // fbx
	public float Scale;
	public Vector3 Offset;
	public string TargetArmatureType;

	public Poses.PoseAnimation Animation { get; private set; }

	Transform target;

	public override void Init() {
		target = SceneManager.Instance.ArmatureInUse.transform;

		Poses.LoadFBX(AnimObjAssetPath, out var model, out var clip);

		Animation = Poses.GeneratePoseAnim(model, clip);

		Animation.Scale(Scale);
	}

	public override void UpdateState(ulong time) {
		var pose = Animation.Sample(time);

		Poses.CopyPose(pose, target);

		target.position = Offset;
	}
}