using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public abstract class DVSampledMotion : DVMotion {
	public abstract float SampleRate { get; }
}