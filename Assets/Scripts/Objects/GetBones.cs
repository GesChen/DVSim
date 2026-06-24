using System.Linq;
using UnityEngine;

public class GetBones : MonoBehaviour {
	public Transform hips;
	private void Start() {
		Debug.Log(string.Join(", ", GetComponent<SkinnedMeshRenderer>().bones.Select(b => b.name)));
		Debug.Log(string.Join(", ", hips.GetComponentsInChildren<Transform>().Select(t =>  t.name)));
	}
}