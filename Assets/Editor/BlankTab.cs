using UnityEditor;

public class BlankTab : EditorWindow {
	[MenuItem("Window/Blank Tab")]
	public static void ShowWindow() {
		GetWindow<BlankTab>("Blank");
	}
}