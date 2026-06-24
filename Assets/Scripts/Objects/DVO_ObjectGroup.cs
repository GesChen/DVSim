using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_ObjectGroup : DVObject {
	public List<DVObject> Objects;

	public override void Init() {
		foreach (var obj in Objects) {
			obj.Init();
		}
	}

	public override void UpdateState(ulong time) {
		foreach (var obj in Objects) {
			obj.UpdateState(time);
		}
	}
}