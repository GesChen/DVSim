using System.Collections;
using System.Collections.Generic;
using UnityEngine;
public class SceneManager : Singleton<SceneManager> {
	public Transform EnvironmentContainer;
	public Transform ObjectsContainer;
	public Transform ModelContainer;
	public Transform LightingContainer;
	public Transform CameraContainer;
	public Transform Armature;
	public Transform AnimationContainer;
}