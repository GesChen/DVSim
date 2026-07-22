Shader "Hidden/ObjectIdDepth"
{
    SubShader
    {
        Tags
        {
            "RenderPipeline" = "UniversalPipeline"
            "RenderType" = "Opaque"
        }

        Pass
        {
            Name "ObjectIdDepth"

            ZWrite On
            ZTest LEqual
            Cull Back

            HLSLPROGRAM

            #pragma vertex Vert
            #pragma fragment Frag

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                uint _ID;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float  eyeDepth  : TEXCOORD0;
            };

            struct FragmentOutput
            {
                uint  objectId : SV_Target0;
                float depth    : SV_Target1;
            };

            Varyings Vert(Attributes input)
            {
                Varyings output;

                VertexPositionInputs positionInputs =
                    GetVertexPositionInputs(input.positionOS.xyz);

                output.positionCS = positionInputs.positionCS;
                output.eyeDepth = -positionInputs.positionVS.z;

                return output;
            }

            FragmentOutput Frag(Varyings input)
            {
                FragmentOutput output;
                output.objectId = _ID;
                output.depth = input.eyeDepth;
                return output;
            }

            ENDHLSL
        }
    }
}