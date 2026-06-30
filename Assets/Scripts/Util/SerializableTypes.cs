using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

using System;
using UnityEngine;

[Serializable]
public class S_Vector3 {
	public float x;
	public float y;
	public float z;

	public S_Vector3() { }

	public S_Vector3(float x, float y, float z) {
		this.x = x;
		this.y = y;
		this.z = z;
	}

	public S_Vector3(Vector3 v) {
		x = v.x;
		y = v.y;
		z = v.z;
	}

	public static explicit operator Vector3(S_Vector3 v) =>
		new(v.x, v.y, v.z);

	public static explicit operator S_Vector3(Vector3 v) =>
		new(v);
}

[Serializable]
public class S_Quaternion {
	public float x;
	public float y;
	public float z;
	public float w;

	public S_Quaternion() { }

	public S_Quaternion(float x, float y, float z, float w) {
		this.x = x;
		this.y = y;
		this.z = z;
		this.w = w;
	}

	public S_Quaternion(Quaternion q) {
		x = q.x;
		y = q.y;
		z = q.z;
		w = q.w;
	}

	public static explicit operator Quaternion(S_Quaternion q) =>
		new(q.x, q.y, q.z, q.w);

	public static explicit operator S_Quaternion(Quaternion q) =>
		new(q);
}