using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SceneManager : Singleton<SceneManager> {
	public Transform ArmatureGroup;
	public DVO_Armature[] Armatures;
	public DVO_Armature ArmatureInUse;
	public DVPermutationGroup Lightings;

	public double CurrentSceneLengthSeconds;

	public List<DVObject> SetSceneFromPermutation(int[] permutation, List<DVPermutationGroup> groups) {
		Armatures = ArmatureGroup.GetComponentsInChildren<DVO_Armature>();

		List<DVObject> newObjs = new();

		for (int i = 0; i < permutation.Length; i++) {
			// disable all other items in group
			// there is smarter way yes but im not doing that rn
			var g = groups[i];
			foreach (var obj in g.Objects) {
				obj.gameObject.SetActive(false);
			}

			var desired = g.Objects[permutation[i]];
			desired.gameObject.SetActive(true);
			newObjs.Add(desired);
			newObjs.AddRange(desired.AllSubObjects);

			if (desired.TryGetComponent(out DVO_PoseAnim anim)) {
				// find armature type from the animation
				string tatype = anim.TargetArmatureType;
				ArmatureInUse = Armatures.First(a => a.Type == tatype);
			}
		}

		foreach (var obj in newObjs) {
			obj.GenerateID();
		}

		return newObjs;
	}

	public void InitializeHumanModel(List<DVObject> objs) {
		foreach (var obj in objs) {
			if (obj.TryGetComponent<DVO_HumanModel>(out DVO_HumanModel model)) {
				model.SetToCurArmature();
			}
		}
	}

	public void LoadLighting(DVO_Lighting lighting) {
		foreach (var obj in Lightings.Objects) {
			obj.gameObject.SetActive(false);
		}

		lighting.gameObject.SetActive(true);
		lighting.Init();
		Debug.Log($"Loaded lighting \"{lighting.Label}\"");
	}
}