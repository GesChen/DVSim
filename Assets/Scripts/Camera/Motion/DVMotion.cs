using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public abstract class DVMotion : MonoBehaviour {
	public abstract void Initialize();
	public abstract (Vector3 pos, Quaternion rot) SampleMotion(ulong t);
}