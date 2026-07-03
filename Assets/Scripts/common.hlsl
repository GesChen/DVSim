#define PI 3.14156
#define ln10 2.30258509

// https://www.pcg-random.org/
uint4 pcg4d(inout uint4 v)
{
	v = v * 1664525u + 1013904223u;
	v.x += v.y * v.w;
	v.y += v.z * v.x;
	v.z += v.x * v.y;
	v.w += v.y * v.z;

	v ^= v >> 16;

	v.x += v.y * v.w;
	v.y += v.z * v.x;
	v.z += v.x * v.y;
	v.w += v.y * v.z;

	return v;
}

float rand(inout uint4 s) { return float(pcg4d(s).x) / float(0xffffffffu); }

uint4 coord2seed(uint3 id) {
	return uint4(
		id.x,
		id.y,
		id.x ^ id.y,
		id.x * 1664525u + id.y * 1013904223u);
}

uint4 seededcoord2seed(uint3 id, int seed)
{
	uint useed = asuint(seed);
	return uint4(
		id.x ^ (useed * 0x9E3779B9u),
		id.y ^ (useed * 0xBB67AE85u),
		(id.x ^ id.y) ^ (useed * 0x3C6EF372u),
		id.x * 1664525u + id.y * 1013904223u + useed * 0xA54FF53Au
	);
}

// src: A Note on the Generation of Random Normal Deviates.
// https://doi.org/10.1214/aoms/1177706645
float boxMullerRandomNormal(inout uint4 s)
{
	float u1 = max(rand(s), 1e-7);
	float u2 = rand(s);

	return sqrt(-2.0f * log(u1)) * cos(2.0f * PI * u2);
}