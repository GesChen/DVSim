using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public abstract class DVMotion : MonoBehaviour {
	public abstract void Initialize();
	public abstract void UpdateMotion(ulong t);
}