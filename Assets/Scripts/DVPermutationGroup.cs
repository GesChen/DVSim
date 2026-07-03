using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class DVPermutationGroup : MonoBehaviour {
	[HideInInspector] public List<DVObject> Objects = new();

	private void Awake() {
		foreach (Transform child in transform) {
			if (!child.TryGetComponent<DVObject>(out var dvObj)) 
				Debug.LogWarning($"{child.name} does not have DVObject component, will not be part of permutation group");

			Objects.Add(dvObj);

			child.gameObject.SetActive(false);
		}
	}
}