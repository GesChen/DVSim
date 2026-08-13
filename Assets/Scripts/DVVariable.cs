using System.Collections;
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class DVVariable : MonoBehaviour {
	[HideInInspector] public List<DVObject> Objects = new();
	[Serializable]
	public struct Variation {
		// i dont remember why i added this, it may come back later 
		//public bool Single; // might change to count
		[Serializable]
		public struct Possibility {
			public DVObject obj;
			[Range(0, 1)] public float probability;
		}
		[SerializeField]
		public List<Possibility> Possibilities;
	}
	[Tooltip("Leave blank to directly use objects")]
	public List<Variation> Variations;
	

	[HideInInspector] public int[] activeObjects;

	private void Awake() {
		foreach (Transform child in transform) {
			if (!child.TryGetComponent<DVObject>(out var dvObj)) 
				Debug.LogWarning($"{child.name} does not have DVObject component, will not be part of permutation group");

			Objects.Add(dvObj);

			child.gameObject.SetActive(false);
		}
	}

	public void ApplySubPermutation(int subIndex, int iterationSeed) {
		if (Variations.Count > 0 && (subIndex < 0 || subIndex >= Variations.Count)) {
			Debug.LogError($"SubPermutation index {subIndex} is out of range");
			return;
		}

		foreach (var obj in Objects) {
			obj.gameObject.SetActive(false);
		}

		if (Variations.Count > 0) {
			UnityEngine.Random.InitState(HashCode.Combine(DVConfig.Seed, iterationSeed));
			var sub = Variations[subIndex];
			foreach (var chance in sub.Possibilities) {
				if (UnityEngine.Random.value < chance.probability) {
					chance.obj.gameObject.SetActive(true);
				}
			}
		} else {
			Objects[subIndex].gameObject.SetActive(true);
		}

		activeObjects = Objects.Select((obj, index) => obj.gameObject.activeSelf ? index : -1).Where(index => index != -1).ToArray();
	}
}