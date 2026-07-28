using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_Weather : DVObject {
	public double timeScale;
	public ParticleSystem ps;
	ulong lastTime;
	public override void Init() {
		ps = GetComponent<ParticleSystem>();
		ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

		ps.useAutoRandomSeed = false;
		ps.randomSeed = unchecked((uint)DVConfig.Seed);
		var main = ps.main;
		main.simulationSpeed = (float)(1 / timeScale);

		ps.Play(true);
		ps.Pause(true);
		ps.Simulate(0, true, true, false);
	}

	public override void UpdateState(ulong time) {
		if (time < lastTime) 
			ps.Simulate(
				(float)((double)(time - lastTime) / DVConfig.timeScale * timeScale),
				true, false, false);
		else
			ps.Simulate(
				(float)((double)time / DVConfig.timeScale * timeScale),
				true, true, false);
		lastTime = time;
	}

	public override DVSMemory.BBox GenerateBBoxExact(Camera camera) {
		return new DVSMemory.BBox() { rendered = false };
	}
}