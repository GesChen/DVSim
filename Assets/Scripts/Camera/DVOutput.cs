using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// wrapper for a single modality
// lets do this later if it really gets complicated.. 
// ^ i dont want to do this right now....
public abstract class DVOutput {
	DVS Parent;
	protected void Register(DVS parent) {
		Parent = parent;
	}
	public abstract void Init();
	public abstract void Tick();
	public abstract void Cleanup();
}