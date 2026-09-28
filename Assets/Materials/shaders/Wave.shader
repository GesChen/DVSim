Shader "Custom/Wave"
{
    Properties
    {
        _BaseMap        ("Diffuse (RGBA)", 2D) = "white" {}
        _NormalMap      ("Normal Map", 2D) = "bump" {}
        _Color          ("Tint", Color) = (1, 1, 1, 1)

        _NormalStrength ("Normal Strength", Range(0, 2)) = 1
        _Cutoff         ("Alpha Cutoff", Range(0, 1)) = 0.3

        [Toggle]
        _UseEmission    ("Emission", Int) = 0

        _EmissionMap    ("Emission Map", 2D) = "black" {}
        _EmissionIntensity ("Emission Intensity", Range(0, 10)) = 1

        [Toggle]
        _WaveEnabled    ("Enable Wave", Int) = 1

        [Toggle(_PREVIEW_WAVE)]
        _PreviewWave    ("Preview Wave", Float) = 0

        _Phase          ("Wave Phase", Float) = 0
        _PreviewSpeed   ("Preview Speed", Float) = 1

        _WaveStrength   ("Wave Strength", Range(0, 1)) = 0.15
        _WaveFrequency  ("Wave Frequency", Float) = 1.5
        _NoiseScale     ("Noise Scale", Float) = 0.8
        _NoiseStrength  ("Noise Strength", Range(0, 1)) = 0.35
        _YWaveFactor    ("Y Wave Factor", Range(0, 1)) = 0

        [Toggle(_TIP_POWER)]
        _UseTipPower    ("Use Tip Power", Float) = 1

        _TipPower       ("Tip Weight Power", Range(0.25, 4)) = 1.5
    }

    SubShader
    {
        Tags
        {
            "RenderType" = "Opaque"
            "Queue" = "Geometry"
            "RenderPipeline" = "UniversalPipeline"
        }

        Cull Off
        ZWrite On

        HLSLINCLUDE

        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        TEXTURE2D(_BaseMap);
        SAMPLER(sampler_BaseMap);

        TEXTURE2D(_NormalMap);
        SAMPLER(sampler_NormalMap);

        TEXTURE2D(_EmissionMap);
        SAMPLER(sampler_EmissionMap);

        CBUFFER_START(UnityPerMaterial)
            float4 _BaseMap_ST;
            float4 _Color;

            float _NormalStrength;
            float _Cutoff;

            int _UseEmission;
            float _EmissionIntensity;

            int _WaveEnabled;

            float _PreviewWave;
            float _Phase;
            float _PreviewSpeed;

            float _WaveStrength;
            float _WaveFrequency;
            float _NoiseScale;
            float _NoiseStrength;
            float _YWaveFactor;

            float _UseTipPower;
            float _TipPower;
        CBUFFER_END

        float Hash21(float2 p)
        {
            p = frac(p * float2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return frac(p.x * p.y);
        }

        float ValueNoise(float2 p)
        {
            float2 cell = floor(p);
            float2 local = frac(p);

            local = local * local * (3.0 - 2.0 * local);

            float a = Hash21(cell);
            float b = Hash21(cell + float2(1.0, 0.0));
            float c = Hash21(cell + float2(0.0, 1.0));
            float d = Hash21(cell + float2(1.0, 1.0));

            return lerp(
                lerp(a, b, local.x),
                lerp(c, d, local.x),
                local.y
            );
        }

        float GetWavePhase()
        {
            #if defined(_PREVIEW_WAVE)
                return _Time.y * _PreviewSpeed;
            #else
                return _Phase;
            #endif
        }

        float3 ApplyWave(float3 positionWS, float2 uv)
        {
            // Global runtime toggle.
            // Disabled = preserve the original vertex position exactly.
            if (_WaveEnabled == 0)
                return positionWS;

            float timePhase = GetWavePhase();

            float tipWeight = saturate(uv.y);

            #if defined(_TIP_POWER)
                tipWeight = pow(tipWeight, _TipPower);
            #endif

            float2 noisePosition =
                positionWS.xz * _NoiseScale +
                float2(
                    timePhase * 0.17,
                    timePhase * 0.11
                );

            float noise =
                ValueNoise(noisePosition) * 2.0 - 1.0;

            float wavePhase =
                dot(
                    positionWS.xz,
                    float2(0.73, 1.17)
                )
                * _WaveFrequency
                + timePhase
                + noise * _NoiseStrength * 3.0;

            float3 wave = float3(
                sin(wavePhase),
                sin(wavePhase * 0.67 + noise * 1.37)
                    * _YWaveFactor,
                cos(wavePhase * 0.83 + noise * 2.0)
            );

            float amplitude =
                _WaveStrength
                * tipWeight
                * (1.0 + noise * _NoiseStrength);

            positionWS += wave * amplitude;

            return positionWS;
        }

        ENDHLSL

        Pass
        {
            Name "ForwardLit"

            Tags
            {
                "LightMode" = "UniversalForward"
            }

            HLSLPROGRAM

            #pragma vertex Vert
            #pragma fragment Frag

            #pragma shader_feature_local _PREVIEW_WAVE
            #pragma shader_feature_local _TIP_POWER

            #pragma multi_compile_fragment _ _MAIN_LIGHT_SHADOWS
            #pragma multi_compile_fragment _ _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile_fog

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS   : NORMAL;
                float4 tangentOS  : TANGENT;
                float2 uv         : TEXCOORD0;
            };

            struct Varyings
            {
                float4 positionCS  : SV_POSITION;
                float3 positionWS  : TEXCOORD0;
                float2 uv          : TEXCOORD1;
                float3 normalWS    : TEXCOORD2;
                float3 tangentWS   : TEXCOORD3;
                float3 bitangentWS : TEXCOORD4;
                float fogFactor    : TEXCOORD5;
            };

            Varyings Vert(Attributes input)
            {
                Varyings output;

                float3 positionWS =
                    TransformObjectToWorld(
                        input.positionOS.xyz
                    );

                positionWS =
                    ApplyWave(positionWS, input.uv);

                VertexNormalInputs normalInputs =
                    GetVertexNormalInputs(
                        input.normalOS,
                        input.tangentOS
                    );

                output.positionCS =
                    TransformWorldToHClip(positionWS);

                output.positionWS = positionWS;

                output.uv =
                    TRANSFORM_TEX(
                        input.uv,
                        _BaseMap
                    );

                output.normalWS =
                    normalInputs.normalWS;

                output.tangentWS =
                    normalInputs.tangentWS;

                output.bitangentWS =
                    normalInputs.bitangentWS;

                output.fogFactor =
                    ComputeFogFactor(
                        output.positionCS.z
                    );

                return output;
            }

            half4 Frag(
                Varyings input,
                bool isFrontFace : SV_IsFrontFace
            ) : SV_Target
            {
                half4 baseColor =
                    SAMPLE_TEXTURE2D(
                        _BaseMap,
                        sampler_BaseMap,
                        input.uv
                    ) * _Color;

                clip(baseColor.a - _Cutoff);

                half3 normalTS =
                    UnpackNormalScale(
                        SAMPLE_TEXTURE2D(
                            _NormalMap,
                            sampler_NormalMap,
                            input.uv
                        ),
                        _NormalStrength
                    );

                half3 normalWS =
                    normalize(
                        normalTS.x * input.tangentWS +
                        normalTS.y * input.bitangentWS +
                        normalTS.z * input.normalWS
                    );

                normalWS *=
                    isFrontFace ? 1.0h : -1.0h;

                float4 shadowCoord =
                    TransformWorldToShadowCoord(
                        input.positionWS
                    );

                Light mainLight =
                    GetMainLight(shadowCoord);

                half NdotL =
                    saturate(
                        dot(
                            normalWS,
                            mainLight.direction
                        )
                    );

                half3 ambient =
                    SampleSH(normalWS);

                half3 direct =
                    mainLight.color *
                    NdotL *
                    mainLight.distanceAttenuation *
                    mainLight.shadowAttenuation;

                half3 finalColor =
                    baseColor.rgb *
                    (ambient + direct);

                if (_UseEmission != 0)
                {
                    half3 emission =
                        SAMPLE_TEXTURE2D(
                            _EmissionMap,
                            sampler_EmissionMap,
                            input.uv
                        ).rgb;

                    finalColor +=
                        emission * _EmissionIntensity;
                }

                finalColor =
                    MixFog(
                        finalColor,
                        input.fogFactor
                    );

                return half4(finalColor, 1.0h);
            }

            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"

            Tags
            {
                "LightMode" = "ShadowCaster"
            }

            Cull Off
            ZWrite On
            ColorMask 0

            HLSLPROGRAM

            #pragma vertex ShadowVert
            #pragma fragment ShadowFrag

            #pragma shader_feature_local _PREVIEW_WAVE
            #pragma shader_feature_local _TIP_POWER

            struct ShadowAttributes
            {
                float4 positionOS : POSITION;
                float2 uv         : TEXCOORD0;
            };

            struct ShadowVaryings
            {
                float4 positionCS : SV_POSITION;
                float2 uv         : TEXCOORD0;
            };

            ShadowVaryings ShadowVert(
                ShadowAttributes input
            )
            {
                ShadowVaryings output;

                float3 positionWS =
                    TransformObjectToWorld(
                        input.positionOS.xyz
                    );

                positionWS =
                    ApplyWave(
                        positionWS,
                        input.uv
                    );

                output.positionCS =
                    TransformWorldToHClip(
                        positionWS
                    );

                output.uv =
                    TRANSFORM_TEX(
                        input.uv,
                        _BaseMap
                    );

                return output;
            }

            half4 ShadowFrag(
                ShadowVaryings input
            ) : SV_Target
            {
                half alpha =
                    SAMPLE_TEXTURE2D(
                        _BaseMap,
                        sampler_BaseMap,
                        input.uv
                    ).a * _Color.a;

                clip(alpha - _Cutoff);

                return 0;
            }

            ENDHLSL
        }
    }
}