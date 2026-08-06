using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;

public abstract class DVObject : MonoBehaviour {
	public string LabelOverride;

	public string Label => LabelOverride.Length > 0 ? LabelOverride : gameObject.name;

	[HideInInspector] public DVObject[] AllSubObjects;
	void Awake() {
		AllSubObjects = transform.GetComponentsInChildren<DVObject>().Where(o => o != this).ToArray();
	}

	public Renderer Renderer => HF.LoadCached(ref m_renderer, () => {
		if (checkedR) return null;
		var r = GetComponent<Renderer>();
		checkedR = true;
		return r;
	});
	Renderer m_renderer;
	bool checkedR;

	public MeshFilter filter => HF.LoadCached(ref m_filter, () => GetComponent<MeshFilter>());
	MeshFilter m_filter;

	public Vector3[] localVerts => HF.LoadCached(ref m_localVerts, () => filter.mesh.vertices);
	Vector3[] m_localVerts;

	public abstract void Init();
	public abstract void UpdateState(ulong time);

	public uint ID;
	public void GenerateID() {
		string identifier = $"{transform.gameObject.scene.name}/{GetCanonicalObjectPath(transform.gameObject.transform)}";
		ID = Fnv1a32(identifier);

		var propertyBlock = new MaterialPropertyBlock();

		if (Renderer == null) {
			//Debug.LogWarning($"{gameObject.name} has no renderer, will not get ID mpb");
			return; // still has an id just not renderable one 
		}

		Renderer.GetPropertyBlock(propertyBlock);
		propertyBlock.SetInteger("_ID", unchecked((int)ID));
		Renderer.SetPropertyBlock(propertyBlock);
		//Debug.Log($"registered id property for {gameObject.name}");
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


	// imprecise implementation for now, fast but rough and not exact
	// using dvsmemory.bbox here is bad code but whatever
	public DVSMemory.BBox GenerateBBoxFast(Camera camera) {
		if (Renderer == null) return new() { rendered = false };

		var wsBounds = Renderer.bounds;

		// too lazy to write myself 
		// https://discussions.unity.com/t/is-there-an-easy-way-to-get-on-screen-render-size-bounds/15884/3
		Vector3 cen = wsBounds.center;
		Vector3 ext = wsBounds.extents;

		Vector3[] extentPoints = new Vector3[8] {
			new (cen.x-ext.x, cen.y-ext.y, cen.z-ext.z),
			new (cen.x+ext.x, cen.y-ext.y, cen.z-ext.z),
			new (cen.x-ext.x, cen.y-ext.y, cen.z+ext.z),
			new (cen.x+ext.x, cen.y-ext.y, cen.z+ext.z),

			new (cen.x-ext.x, cen.y+ext.y, cen.z-ext.z),
			new (cen.x+ext.x, cen.y+ext.y, cen.z-ext.z),
			new (cen.x-ext.x, cen.y+ext.y, cen.z+ext.z),
			new (cen.x+ext.x, cen.y+ext.y, cen.z+ext.z)
		};

		Vector2 min = Vector2.positiveInfinity;
		Vector2 max = Vector2.negativeInfinity;

		foreach (Vector3 v3 in extentPoints) {
			Vector2 v2 = camera.WorldToScreenPoint(v3);

			min = Vector2.Min(min, v2);
			max = Vector2.Max(max, v2);
		}
		DebugExtra.DrawRectSS(min, max, camera, drawGame: true, duration: .1f);

		return new() {
			min = (S_Vector2)min,
			max = (S_Vector2)max,
			distance = (camera.transform.position - cen).magnitude,
			rendered = true,
		};
	}

	// slow since it needs to do all this calculation
	public virtual DVSMemory.BBox GenerateBBoxExact(Camera camera) {
		if (Renderer == null) return new() { rendered = false };

		Vector3[] wsVerts = localVerts.ToArray();
		transform.TransformPoints(wsVerts);

		Vector2 min = Vector2.positiveInfinity;
		Vector2 max = Vector2.negativeInfinity;
		Vector3 total = Vector3.zero;

		foreach (Vector3 v3 in wsVerts) {
			Vector2 v2 = camera.WorldToScreenPoint(v3);

			min = Vector2.Min(min, v2);
			max = Vector2.Max(max, v2);
			total += v3;
			//DebugExtra.DrawPoint(v3, duration: .1f);
		}
		Vector3 center = total / wsVerts.Length;
		//DebugExtra.DrawRectSS(min, max, camera, drawGame: true, duration: .3f);

		return new() {
			min = (S_Vector2)min,
			max = (S_Vector2)max,
			distance = (camera.transform.position - center).magnitude,
			rendered = true,
		};
	}
}