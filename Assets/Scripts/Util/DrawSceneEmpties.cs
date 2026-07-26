using UnityEngine;

[ExecuteAlways]
public class DrawSceneEmpties : MonoBehaviour {
	public bool draw = true;
	public Color color = Color.yellow;
	public float size = 0.1f;

	void Update() {
		if (!draw)
			return;

		foreach (Transform t in FindObjectsByType<Transform>(FindObjectsSortMode.None)) {
			if (t.GetComponents<Component>().Length == 1)
				DebugExtra.DrawEmpty(t.position, size, color);
		}
	}
}