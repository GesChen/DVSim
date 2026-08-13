using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_Pedestrian : DVO_Vehicle {
	public DVO_Armature armature;
	public Quaternion rotationDelta;

	public float minScale;
	public float maxScale;

	float blendFactor;
	ulong phaseOffset;

	const string AnimSrc1 = "Assets/Assets/humans/occluders/walk 1 39_13.fbx";
	const string AnimSrc2 = "Assets/Assets/humans/occluders/walk 2 39_14.fbx";

	static Poses.PoseAnimation anim1;
	static Poses.PoseAnimation anim2;
	static float animLength;

	public static Texture2D[] SMPLitexTextures;

	DVO_PedestrianPart lowResPart => HF.LoadCached(ref m_lrp, () => LowRes as DVO_PedestrianPart);
	DVO_PedestrianPart m_lrp;

	DVO_PedestrianPart hiResPart => HF.LoadCached(ref m_hrp, () => HiRes as DVO_PedestrianPart);
	DVO_PedestrianPart m_hrp;

	protected override void InitVehicle() {
		SMPLitexTextures ??= Resources.LoadAll<Texture2D>("SMPLitex_occlude");

		if (anim1 == null && Application.isPlaying) {
			Poses.LoadFBX(AnimSrc1, out var bm1, out var clip1);
			anim1 = Poses.GeneratePoseAnim(bm1, clip1);

			Poses.LoadFBX(AnimSrc2, out var bm2, out var clip2);
			anim2 = Poses.GeneratePoseAnim(bm2, clip2);

			animLength = anim1.Duration;
		}

		Random.InitState(unchecked((int)ID));
		blendFactor = Random.Range(0.0f, 1.0f);
		phaseOffset = (ulong)(Random.Range(0, animLength) * DVConfig.timeScale);
		armature.transform.localScale = Random.Range(minScale, maxScale) * Vector3.one;
	}

	protected override void Randomize() {
		lowResPart.Randomize(ID);
		hiResPart.Randomize(ID);
	}

	public override void UpdateState(ulong time) {
		if (!Application.isPlaying) return; // too buggy

		time += phaseOffset;
		time %= (ulong)(animLength * DVConfig.timeScale);

		Poses.Pose sample1 = anim1.Sample(time);
		Poses.Pose sample2 = anim2.Sample(time);

		Poses.Pose pose = Poses.Pose.Lerp(sample1, sample2, blendFactor);

		armature.ApplyPose(pose);
		armature.RootBoneTransform.SetLocalPositionAndRotation(
			armature.groundingOffset,
			armature.RootBoneTransform.localRotation * rotationDelta);

		// this isnt the worst thing ive ever seen
		(UsingHiRes ? hiResPart : lowResPart).UpdateState(time);
	}
}