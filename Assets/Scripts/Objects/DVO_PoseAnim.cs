using UnityEngine;

public class DVO_PoseAnim : DVObject {
	public string AnimObjAssetPath; // fbx
	public float Scale;

	public Poses.PoseAnimation Animation { get; private set; }

	Transform target;

	public override void Init() {
		target = SceneManager.Instance.Armature;

		Poses.LoadFBX(AnimObjAssetPath, out var model, out var clip);

		Animation = Poses.GeneratePoseAnim(model, clip);

		Animation.Scale(Scale);
	}

	public override void UpdateState(ulong time) {
		var pose = Animation.Sample(time);

		Poses.CopyPose(pose, target);
	}
}