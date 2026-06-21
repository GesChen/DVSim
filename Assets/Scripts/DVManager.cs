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
		foreach (var obj in Objects) {
			obj.UpdateState();
		}
		
		foreach (var sensor in Sensors) {
			sensor.Tick();
		}

		Frame++;
		Time = (ulong)Math.Round(Frame * 1_000_000_000.0 / DVConfig.SimFPS);
	}

	private void Awake() {
		Frame = 0;
	}

	private void LateUpdate() {
		Tick();
	}
}