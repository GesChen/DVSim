using System.Linq;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using static DVManager;

public class SceneManager : Singleton<SceneManager> {
	public Transform EnvironmentContainer;
	public Transform ObjectsContainer;
	public Transform ModelContainer;
	public Transform LightingContainer;
	public Transform Armature;
	public Transform AnimationContainer;

	public double CurrentSceneLengthSeconds;

	public void ClearScene() {
		static void ClearContainer(Transform container) {
			foreach (Transform child in container) 
				DestroyImmediate(child.gameObject);
		}

		ClearContainer(EnvironmentContainer);
		ClearContainer(ObjectsContainer);
		ClearContainer(ModelContainer);
		ClearContainer(LightingContainer);
		ClearContainer(AnimationContainer);
	}

	public List<DVObject> CreateSceneFromPermutations(int[] permutation, List<PermutationGroup> groups) {

		// what the fuck are you doing.
		GameObject FindPerm(string name, int permI) => groups.First(g => g.Category == name).Objects[permutation[permI]].gameObject;

		return CreateScene(
			FindPerm("Environments", 0),
			FindPerm("Objects", 1),
			FindPerm("Models", 2),
			FindPerm("Lightings", 3),
			FindPerm("Animations", 4));
	}



	public List<DVObject> CreateScene(
		GameObject environment,
		GameObject objects,
		GameObject model,
		GameObject lighting,
		GameObject animation) {

		List<DVObject> dvObjs = new();

		void Create(GameObject obj, Transform container) {
			var newObj = Instantiate(obj, container);
			dvObjs.Add(newObj.GetComponent<DVObject>());
		}

		Create(environment, EnvironmentContainer);
		Create(objects, ObjectsContainer);
		Create(model, ModelContainer);
		Create(lighting, LightingContainer);
		Create(animation, AnimationContainer);

		return dvObjs;
	}
}