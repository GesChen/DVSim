using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class PoseCopy {

	public class PoseAnimation {
		public Pose[] Poses;
		public float fps;

		public Pose GetFrame(int frame) {
			frame = Mathf.Clamp(frame, 0, Poses.Length - 1);
			return Poses[frame];
		}

		public Pose Sample(ulong time) => SampleAnim(time, this);

		public void Scale(float scale) {
			foreach (var p in Poses) {
				p.Scale(scale);
			}
		}
	}

	public class Pose {
		public PoseBone[] Bones;

		public void Scale(float scale) {
			foreach (var b in Bones) {
				b.Scale(scale);
			}
		}
	}

	public class PoseBone {
		public string Name;
		public Vector3 Position;
		public Quaternion Rotation;

		public void Scale(float scale) {
			Position *= scale;
		}
	}

	public static void LoadFBX(string assetPath, out GameObject boneModel, out AnimationClip clip) {
		boneModel = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);

		clip = AssetDatabase.LoadAllAssetsAtPath(assetPath)
			.OfType<AnimationClip>()
			.First(c => !c.name.StartsWith("__preview__"));
	}

	public static PoseAnimation GeneratePoseAnim(GameObject boneModel, AnimationClip clip) {
		PoseAnimation anim = new();
		
		float fps = clip.frameRate;
		anim.fps = fps;

		int frames = (int)(clip.length * fps);
		anim.Poses = new Pose[frames];

		// setup anim
		GameObject model = GameObject.Instantiate(boneModel);

		List<string> names = new();
		List<Transform> boneObjs = new();
		foreach (Transform t in model.GetComponentsInChildren<Transform>()) {
			if (t == model.transform) continue;

			if (names.Contains(t.name)) {
				Debug.LogError("Pose generation failed: Bone model contains duplicate names");
				return null;
			}

			names.Add(t.name);
			boneObjs.Add(t);
		}

		for (int f = 0; f < frames; f++) {
			// sample at specific frame

			// can only sample with time though. convert back to time
			clip.SampleAnimation(model, f / fps);

			PoseBone[] bones = new PoseBone[names.Count];
			for (int b = 0; b < bones.Length; b++) {
				bones[b] = new() {
					Name = names[b],
					Position = boneObjs[b].localPosition,
					Rotation = boneObjs[b].localRotation,
				};
			}

			Pose pose = new() {
				Bones = bones
			};

			anim.Poses[f] = pose;
		}

		GameObject.Destroy(model);

		return anim;
	}

	public static Pose SampleAnim(ulong time, PoseAnimation anim) {
		// sample 4 points for time interpolation

		// convert time to seconds 
		double t = (double)time / DVConfig.TimeScale;

		// find closest 4 frames around t bounded by src clip
		// t0---t1-t--t2---t3

		float fps = anim.fps;
		int f_1 = (int)(t * fps); // faster floor
		Pose p0 = anim.GetFrame(f_1 - 1);
		Pose p1 = anim.GetFrame(f_1 - 0);
		Pose p2 = anim.GetFrame(f_1 + 1);
		Pose p3 = anim.GetFrame(f_1 + 2);

		// generate new bones
		int bonecount = p0.Bones.Length;

		PoseBone[] newBones = new PoseBone[bonecount];
		for (int i = 0; i < bonecount; i++)
			newBones[i] = new() { Name = p0.Bones[i].Name };

		// get 0-1 t
		double t1 = (double)f_1 / fps;
		double t2 = (double)(f_1 + 1 )/ fps;

		float T = (float)((t - t1) / (t2 - t1));

		// interpolate bones
		for (int i = 0; i < bonecount; i++) {
			PoseBone b0 = p0.Bones[i];
			PoseBone b1 = p1.Bones[i];
			PoseBone b2 = p2.Bones[i];
			PoseBone b3 = p3.Bones[i];

			newBones[i].Position =
				InterpolationMath.CatmullRomVec3Components(
					b0.Position,
					b1.Position,
					b2.Position,
					b3.Position,
					T);

			newBones[i].Rotation =
				InterpolationMath.CatmullLikeQuaternion(
					b0.Rotation,
					b1.Rotation,
					b2.Rotation,
					b3.Rotation,
					T);
		}

		Pose newPose = new() {
			Bones = newBones
		};

		return newPose;
	}

	public static void CopyPose(Pose pose, Transform target) {

		Transform[] targetChildren = target.GetComponentsInChildren<Transform>();
		foreach (var bone in pose.Bones) {
			var targetObj = targetChildren.FirstOrDefault(c => c.name == bone.Name);

			if (targetObj == null) {
				Debug.LogError("Cannot copy pose: Pose and target do not match structures");
				Debug.Log($"Could not find {bone.Name} bone");
				// todo: put this as a pre check im too lazy to do that though
				return;
			}

			targetObj.SetLocalPositionAndRotation(bone.Position, bone.Rotation);
		}
	}
}

public static class InterpolationMath {
	public static Quaternion CatmullLikeQuaternion(
		Quaternion q0,
		Quaternion q1,
		Quaternion q2,
		Quaternion q3,
		float t) {
		Quaternion s1 = SquadTangent(q0, q1, q2);
		Quaternion s2 = SquadTangent(q1, q2, q3);

		return Squad(q1, q2, s1, s2, t);
	}

	public static Quaternion Squad(
		Quaternion q1, // controls
		Quaternion q2,
		Quaternion s1, // tangents
		Quaternion s2,
		float t) {

		// hermite analogue
		Quaternion a = Quaternion.Slerp(q1, q2, t);
		Quaternion b = Quaternion.Slerp(s1, s2, t);
		return Quaternion.Slerp(a, b, 2f * t * (1f - t));
	}

	static Quaternion QLog(Quaternion q) {
		q = Normalize(q);

		float a = Mathf.Acos(Mathf.Clamp(q.w, -1f, 1f));
		float sinA = Mathf.Sin(a);

		if (Mathf.Abs(sinA) < 1e-6f)
			return new Quaternion(0f, 0f, 0f, 0f);

		float coeff = a / sinA;
		return new Quaternion(q.x * coeff, q.y * coeff, q.z * coeff, 0f);
	}

	static Quaternion QExp(Quaternion q) {
		float a = Mathf.Sqrt(q.x*q.x + q.y*q.y + q.z*q.z);
		float sinA = Mathf.Sin(a);

		if (a < 1e-6f)
			return new Quaternion(q.x, q.y, q.z, Mathf.Cos(a));

		float coeff = sinA / a;
		return Normalize(new Quaternion(q.x * coeff, q.y * coeff, q.z * coeff, Mathf.Cos(a)));
	}

	static Quaternion Normalize(Quaternion q) {
		float mag = Mathf.Sqrt(q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w);
		return new Quaternion(q.x / mag, q.y / mag, q.z / mag, q.w / mag);
	}

	static Quaternion SquadTangent(Quaternion qPrev, Quaternion q, Quaternion qNext) {
		qPrev = EnsureSameHemisphere(q, qPrev);
		qNext = EnsureSameHemisphere(q, qNext);

		Quaternion invQ = Quaternion.Inverse(q);

		Quaternion log1 = QLog(invQ * qPrev);
		Quaternion log2 = QLog(invQ * qNext);

		Quaternion avg = new Quaternion(
		-0.25f * (log1.x + log2.x),
		-0.25f * (log1.y + log2.y),
		-0.25f * (log1.z + log2.z),
		0f
	);

		return Normalize(q * QExp(avg));
	}

	static Quaternion EnsureSameHemisphere(Quaternion reference, Quaternion q) {
		if (Quaternion.Dot(reference, q) < 0f)
			return new Quaternion(-q.x, -q.y, -q.z, -q.w);

		return q;
	}

	public static Vector3 CatmullRomVec3Components(
		Vector3 v0,
		Vector3 v1,
		Vector3 v2,
		Vector3 v3,
		float t) =>
		new(
			CatmullRom(v0.x, v1.x, v2.x, v3.x, t),
			CatmullRom(v0.y, v1.y, v2.y, v3.y, t),
			CatmullRom(v0.z, v1.z, v2.z, v3.z, t)
			);


	public static float CatmullRom(float p0, float p1, float p2, float p3, float t) {
		float t2 = t * t;
		float t3 = t2 * t;

		float result =
		0.5f *
		(
			(2.0f * p1) +
			(-p0 + p2) * t +
			(2.0f*p0 - 5.0f*p1 + 4.0f*p2 - p3) * t2 +
			(-p0 + 3.0f*p1 - 3.0f*p2 + p3) * t3
		);

		return result;
	}
}