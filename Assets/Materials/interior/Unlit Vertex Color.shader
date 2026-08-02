Shader "Custom/Unlit Vertex Color"
{
    Properties
    {
    }

    // Universal Render Pipeline
    SubShader
    {
        Tags
        {
            "RenderType" = "Opaque"
            "Queue" = "Geometry"
            "RenderPipeline" = "UniversalPipeline"
        }

        LOD 100

        Pass
        {
            Name "Unlit"
            Tags
            {
                "LightMode" = "UniversalForward"
            }

            Cull Back
            ZWrite On
            ZTest LEqual
            Blend Off

            HLSLPROGRAM

            #pragma target 2.0
            #pragma vertex Vertex
            #pragma fragment Fragment

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct Attributes
            {
                float4 positionOS : POSITION;
                half4 color : COLOR;
            };

            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                half4 color : COLOR;
            };

            Varyings Vertex(Attributes input)
            {
                Varyings output;

                output.positionCS = TransformObjectToHClip(
                    input.positionOS.xyz
                );

                output.color = input.color;

                return output;
            }

            half4 Fragment(Varyings input) : SV_Target
            {
                return input.color;
            }

            ENDHLSL
        }
    }

    // Built-in Render Pipeline
    SubShader
    {
        Tags
        {
            "RenderType" = "Opaque"
            "Queue" = "Geometry"
        }

        LOD 100

        Pass
        {
            Name "Unlit"

            Cull Back
            ZWrite On
            ZTest LEqual
            Blend Off

            CGPROGRAM

            #pragma target 2.0
            #pragma vertex Vertex
            #pragma fragment Fragment

            #include "UnityCG.cginc"

            struct Attributes
            {
                float4 vertex : POSITION;
                fixed4 color : COLOR;
            };

            struct Varyings
            {
                float4 position : SV_POSITION;
                fixed4 color : COLOR;
            };

            Varyings Vertex(Attributes input)
            {
                Varyings output;

                output.position = UnityObjectToClipPos(input.vertex);
                output.color = input.color;

                return output;
            }

            fixed4 Fragment(Varyings input) : SV_Target
            {
                return input.color;
            }

            ENDCG
        }
    }

    Fallback Off
}