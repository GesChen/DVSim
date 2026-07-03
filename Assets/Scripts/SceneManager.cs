using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SceneManager : Singleton<SceneManager> {
	public Transform Armature;

	public double CurrentSceneLengthSeconds;

	public List<DVObject> SetSceneFromPermutation(int[] permutation, List<DVPermutationGroup> groups) {
		List<DVObject> newObjs = new();

		for (int i = 0; i < permutation.Length; i++) {
			// disable all other items in group
			// there is smarter way yes but im not doing that rn
			var g = groups[i];
			foreach (var obj in g.Objects) {
				obj.gameObject.SetActive(false);
			}

			g.Objects[permutation[i]].gameObject.SetActive(true);
			newObjs.Add(g.Objects[permutation[i]]);
		}

		return newObjs;
	}
}