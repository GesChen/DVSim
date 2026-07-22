using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

public abstract class DVObject : MonoBehaviour {
	public abstract void Init();
	public abstract void UpdateState(ulong time);

	public uint ID;
	public void GenerateID() {
		string identifier = $"{transform.gameObject.scene.name}/{GetCanonicalObjectPath(transform.gameObject.transform)}";
		ID = Fnv1a32(identifier);

		var renderer = GetComponent<Renderer>();
		var propertyBlock = new MaterialPropertyBlock();

		if (renderer == null) {
			Debug.LogWarning($"{gameObject.name} has no renderer, will not get ID mpb");
			return; // still has an id just not renderable one 
		}

		renderer.GetPropertyBlock(propertyBlock);
		propertyBlock.SetInteger("_ID", unchecked((int)ID));
		renderer.SetPropertyBlock(propertyBlock);
		Debug.Log($"registered id property for {gameObject.name}");
	}

	// stable string hash, gethashcode is not
	public static uint Fnv1a32(string value) {
		const uint offset = 2166136261;
		const uint prime = 16777619;

		uint hash = offset;

		foreach (byte b in System.Text.Encoding.UTF8.GetBytes(value)) {
			hash ^= b;
			hash *= prime;
		}

		return hash;
	}

	static string GetCanonicalObjectPath(Transform transform) {
		var path = transform.name;

		while (transform.parent != null) {
			transform = transform.parent;
			path = transform.name + "/" + path;
		}

		return path.Replace('\\', '/').ToLowerInvariant();
	}
}