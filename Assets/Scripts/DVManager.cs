using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;

public class DVManager : MonoBehaviour {
	public static ulong Frame; 
	public static ulong Time; // ns

	public List<DVS> Sensors;
	public List<DVObject> Objects;

	public void Tick() {
		Frame++;
		Time = (ulong)Math.Round(Frame * DVConfig.TimeScale / DVConfig.SimFPS);

		foreach (var obj in Objects) {
			obj.UpdateState(Time);
		}
		
		foreach (var sensor in Sensors) {
			sensor.Tick();
		}

	}

	private void Awake() {
		Frame = 0;
	}

	private void LateUpdate() {
		Tick();
	}

	// works to detect scene stop 
	void OnDestroy() {
		foreach (var sensor in Sensors) {
			sensor.events.ForceFlush();
		}
	}
}