using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class DVO_Weather : DVObject {
	public double timeScale;
	public ParticleSystem[] particles;
	ulong lastTime;
	public override void Init() {
		foreach (var ps in particles) {
			ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

			ps.useAutoRandomSeed = false;
			ps.randomSeed = unchecked((uint)DVConfig.Seed);
			var main = ps.main;
			main.simulationSpeed = (float)(1 / timeScale);

			ps.Play(true);
			ps.Pause(true);
			ps.Simulate(0, true, true, false);
		}
	}

	public override void UpdateState(ulong time) {
		if (time > lastTime) 
			foreach (var ps in particles) 
				ps.Simulate(
					(float)((double)(time - lastTime) / DVConfig.timeScale * timeScale),
					true, false, false);
		else // resimulate
			foreach (var ps in particles) 
				ps.Simulate(
					(float)((double)time / DVConfig.timeScale * timeScale),
					true, true, false);
		lastTime = time;
	}

	public override DVSMemory.BBox GenerateBBoxExact(Camera camera) {
		return new DVSMemory.BBox() { rendered = false };
	}
}