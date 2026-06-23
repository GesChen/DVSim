using UnityEngine;

public class posetest : MonoBehaviour
{
	public string path = "Assets/Assets/BVH/01_01.fbx";
	public Transform target;
	public float scale;
	public double time;

	PoseCopy.PoseAnimation anim;
    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
		PoseCopy.LoadFBX(path, out var boneModel, out var clip);

		anim = PoseCopy.GeneratePoseAnim(boneModel, clip);

		anim.Scale(scale);
	}

    // Update is called once per frame
    void Update()
    {
		//var sample = anim.Sample((ulong)(Time.timeAsDouble * DVConfig.TimeScale));
		var sample = anim.Sample((ulong)(time / 100 * DVConfig.TimeScale));

		PoseCopy.CopyPose(sample, target);
	}
}
