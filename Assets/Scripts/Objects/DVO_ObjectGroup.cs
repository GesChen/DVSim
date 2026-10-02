using System;
using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// not much use anymore after the dvo subobjects update
public class DVO_ObjectGroup : DVObject {
	DVObject[] children;
	public override void Init() {
		children = transform.GetComponentsInChildren<DVObject>().Where(o => o.transform != transform).ToArray();
	}

	public override DVObject[] GetSubObjects() => children;

	public override void UpdateState(ulong time) {
		foreach (DVObject o in children) {
			o.UpdateState(time);
		}
	}
}