using System.Collections;
using System.Collections.Generic;
using UnityEngine;
public abstract class DVObject : MonoBehaviour {
	public abstract void UpdateState(ulong time);
}