using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class Hand : MonoBehaviour {
	public Vector3 targetForward;
	public Vector3 targetUp;

	public float pitch;
	public float yaw;
	public float roll;

	public Vector3 pitchPID;
	public Vector3 yawPID;
	public Vector3 rollPID;


	Rigidbody rb;
	ConfigurableJoint joint;

	PidController pidPitch;
	PidController pidYaw;
	PidController pidRoll;

	private void Awake() {
		rb = GetComponent<Rigidbody>();
		joint = GetComponent<ConfigurableJoint>();
		pidPitch = new();
		pidYaw = new();
		pidRoll = new();
	}

	private void FixedUpdate() {
		Vector3 forward = transform.forward;
		Vector3 up = transform.up;

		pidPitch.Kp = pitchPID.x;
		pidPitch.Ki = pitchPID.y;
		pidPitch.Kd = pitchPID.z;
		pidYaw.Kp = yawPID.x;
		pidYaw.Ki = yawPID.y;
		pidYaw.Kd = yawPID.z;
		pidRoll.Kp = rollPID.x;
		pidRoll.Ki = rollPID.y;
		pidRoll.Kd = rollPID.z;

		float forcePitch = pidPitch.Update(targetForward.y, forward.y, Time.deltaTime);
		float forceYaw = pidYaw.Update(targetForward.x, forward.x, Time.deltaTime);
		float forceRoll = pidRoll.Update(targetUp.x, up.x, Time.deltaTime);

		rb.AddRelativeTorque(
			-forcePitch * pitch * Vector3.right + 
			forceYaw * yaw * Vector3.up + 
			-forceRoll * roll * Vector3.forward);
	}
}

public sealed class PidController {
	public float Kp { get; set; } = 1.0f;
	public float Ki { get; set; } = 0.0f;
	public float Kd { get; set; } = 0.0f;

	private float _integral;
	private float _previousError;
	private bool _hasPreviousError;

	public float Update(float setpoint, float measurement, float dt) {
		if (dt <= 0)
			throw new ArgumentOutOfRangeException(nameof(dt), "dt must be positive.");

		float error = setpoint - measurement;

		_integral += error * dt;

		float derivative = 0.0f;
		if (_hasPreviousError)
			derivative = (error - _previousError) / dt;

		float output =
			Kp * error +
			Ki * _integral +
			Kd * derivative;

		_previousError = error;
		_hasPreviousError = true;

		return output;
	}

	public void Reset() {
		_integral = 0;
		_previousError = 0;
		_hasPreviousError = false;
	}
}