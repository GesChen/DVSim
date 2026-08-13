using UnityEngine;
using static Poses;

public class DVO_PoseAnim : DVObject {
	public string AnimObjAssetPath; // fbx
	public float Scale;
	public Vector3 Offset;
	public bool useCustomOffset;
	public string TargetArmatureType;

	public Poses.PoseAnimation Animation { get; private set; }

	DVO_Armature target;
	Quaternion targetInitRot;

	public override void Init() {
		target = DVManager.Instance.ArmatureInUse;
		targetInitRot = target.transform.rotation;

		LoadFBX(AnimObjAssetPath, out var model, out var clip);

		Animation = GeneratePoseAnim(model, clip);

		Animation.Scale(Scale);

		if (!useCustomOffset && DVConfig.doAutoGrounding) {
			Poses.Pose p0 = Animation.Poses[0];
			target.ApplyPose(p0);

			// find feet average
			// aka lowest two bones
			// use first frame
			Vector3 lowest = Vector3.positiveInfinity;
			Vector3 lowest2 = Vector3.positiveInfinity;
			foreach (var joint in target.GetComponentsInChildren<Transform>()) {
				float y = joint.position.y;
				if (y < lowest.y) {
					lowest2 = lowest;
					lowest = joint.position;
				} else if (y < lowest2.y) {
					lowest2 = joint.position;
				}
			}

			Vector3 feetAvg = (lowest + lowest2) / 2f - target.transform.position; // local only

			// find ground
			Vector3 ground = Vector3.zero;
			if (Physics.Raycast(new(transform.position, Vector3.down), out RaycastHit hit))
				ground = hit.point;
			if (Physics.Raycast(new(transform.position, Vector3.up), out RaycastHit hit2)
				&& (ground == Vector3.zero || (ground != Vector3.zero && hit2.point.y < ground.y)))
				ground = hit2.point;

			Offset = ground - feetAvg + target.groundingOffset;

			//DebugExtra.DrawPoint(ground, MoreColors.Red);
			//DebugExtra.DrawPoint(feetAvg, MoreColors.Green);
			//Debug.Break();
		}
	}

	public override void UpdateState(ulong time) {
		var pose = Animation.Sample(time);
		target.ApplyPose(pose);

		target.transform.SetPositionAndRotation(Offset, transform.rotation * targetInitRot);
	}
}