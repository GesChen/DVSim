Shader "Custom/URP/Object World Palette Lit"
{
    Properties
    {
        // Standard URP Lit properties.
        _WorkflowMode("Workflow Mode", Float) = 1.0

        [MainTexture] _BaseMap("Base Map", 2D) = "white" {}
        [MainColor] _BaseColor("Base Color", Color) = (1,1,1,1)

        _Cutoff("Alpha Cutoff", Range(0,1)) = 0.5

        _Smoothness("Smoothness", Range(0,1)) = 0.5
        _SmoothnessTextureChannel("Smoothness Source", Float) = 0

        _Metallic("Metallic", Range(0,1)) = 0
        _MetallicGlossMap("Metallic Map", 2D) = "white" {}

        _SpecColor("Specular Color", Color) = (0.2,0.2,0.2,1)
        _SpecGlossMap("Specular Map", 2D) = "white" {}

        [ToggleOff] _SpecularHighlights("Specular Highlights", Float) = 1
        [ToggleOff] _EnvironmentReflections("Environment Reflections", Float) = 1

        [Normal] _BumpMap("Normal Map", 2D) = "bump" {}
        _BumpScale("Normal Scale", Float) = 1

        _ParallaxMap("Height Map", 2D) = "black" {}
        _Parallax("Height Scale", Range(0.005,0.08)) = 0.005

        _OcclusionMap("Occlusion Map", 2D) = "white" {}
        _OcclusionStrength("Occlusion Strength", Range(0,1)) = 1

        [HDR] _EmissionColor("Emission Color", Color) = (0,0,0,0)
        _EmissionMap("Emission Map", 2D) = "white" {}

        _DetailMask("Detail Mask", 2D) = "white" {}
        _DetailAlbedoMap("Detail Albedo", 2D) = "linearGrey" {}
        _DetailAlbedoMapScale("Detail Albedo Scale", Range(0,2)) = 1

        [Normal] _DetailNormalMap("Detail Normal Map", 2D) = "bump" {}
        _DetailNormalMapScale("Detail Normal Scale", Range(0,2)) = 1

        [Header(Palette)]
        _PaletteColor0("Palette Color 0", Color) = (1,0,0,1)
        _PaletteColor1("Palette Color 1", Color) = (1,0.5,0,1)
        _PaletteColor2("Palette Color 2", Color) = (1,1,0,1)
        _PaletteColor3("Palette Color 3", Color) = (0,1,0,1)
        _PaletteColor4("Palette Color 4", Color) = (0,0.5,1,1)
        _PaletteColor5("Palette Color 5", Color) = (0.25,0,1,1)
        _PaletteColor6("Palette Color 6", Color) = (1,0,1,1)

        // Standard URP surface controls.
        _Surface("__surface", Float) = 0
        _Blend("__blend", Float) = 0
        _Cull("__cull", Float) = 2

        [ToggleUI] _AlphaClip("__clip", Float) = 0
        [ToggleUI] _ReceiveShadows("Receive Shadows", Float) = 1

        [HideInInspector] _SrcBlend("__src", Float) = 1
        [HideInInspector] _DstBlend("__dst", Float) = 0
        [HideInInspector] _SrcBlendAlpha("__srcA", Float) = 1
        [HideInInspector] _DstBlendAlpha("__dstA", Float) = 0
        [HideInInspector] _ZWrite("__zw", Float) = 1
        [HideInInspector] _AlphaToMask("__alphaToMask", Float) = 0

        _QueueOffset("Queue Offset", Float) = 0

        // Compatibility properties expected by URP Lit tooling and passes.
        [HideInInspector] _MainTex("BaseMap", 2D) = "white" {}
        [HideInInspector] _Color("Base Color", Color) = (1,1,1,1)
        [HideInInspector] _GlossMapScale("Smoothness", Float) = 0
        [HideInInspector] _Glossiness("Smoothness", Float) = 0
        [HideInInspector] _GlossyReflections("Environment Reflections", Float) = 0
        [HideInInspector] _ClearCoatMask("Clear Coat Mask", Float) = 0
        [HideInInspector] _ClearCoatSmoothness("Clear Coat Smoothness", Float) = 0
    }

    SubShader
    {
        Tags
        {
            "RenderPipeline" = "UniversalPipeline"
            "RenderType" = "Opaque"
            "UniversalMaterialType" = "Lit"
            "IgnoreProjector" = "True"
        }

        LOD 300

        Pass
        {
            Name "ForwardLit"

            Tags
            {
                "LightMode" = "UniversalForward"
            }

            Blend [_SrcBlend] [_DstBlend], [_SrcBlendAlpha] [_DstBlendAlpha]
            ZWrite [_ZWrite]
            Cull [_Cull]
            AlphaToMask [_AlphaToMask]

            HLSLPROGRAM

            #pragma target 2.0

            #pragma vertex LitPassVertex
            #pragma fragment PaletteLitPassFragment

			#define _NORMALMAP 1
            #pragma shader_feature_local _PARALLAXMAP
            #pragma shader_feature_local _RECEIVE_SHADOWS_OFF
            #pragma shader_feature_local _DETAIL_MULX2
            #pragma shader_feature_local _DETAIL_SCALED

            #pragma shader_feature_local_fragment _SURFACE_TYPE_TRANSPARENT
            #pragma shader_feature_local_fragment _ALPHATEST_ON
            #pragma shader_feature_local_fragment _ALPHAPREMULTIPLY_ON
            #pragma shader_feature_local_fragment _SPECULAR_SETUP
            #pragma shader_feature_local_fragment _METALLICSPECGLOSSMAP
            #pragma shader_feature_local_fragment _SMOOTHNESS_TEXTURE_ALBEDO_CHANNEL_A
            #pragma shader_feature_local_fragment _OCCLUSIONMAP
            #pragma shader_feature_local_fragment _EMISSION
            #pragma shader_feature_local_fragment _SPECULARHIGHLIGHTS_OFF
            #pragma shader_feature_local_fragment _ENVIRONMENTREFLECTIONS_OFF

            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS_SCREEN

            #pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
            #pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS

            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BLENDING
            #pragma multi_compile_fragment _ _REFLECTION_PROBE_BOX_PROJECTION
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
            #pragma multi_compile_fragment _ _LIGHT_COOKIES

            #pragma multi_compile _ _FORWARD_PLUS

            #pragma multi_compile _ LIGHTMAP_SHADOW_MIXING
            #pragma multi_compile _ SHADOWS_SHADOWMASK
            #pragma multi_compile _ DIRLIGHTMAP_COMBINED
            #pragma multi_compile _ LIGHTMAP_ON
            #pragma multi_compile_fog

            #pragma multi_compile_instancing
            #pragma instancing_options renderinglayer

            #include "Packages/com.unity.render-pipelines.universal/Shaders/LitInput.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/Shaders/LitForwardPass.hlsl"

            /*
             * These are serialized material properties because they appear in
             * the Properties block above.
             *
             * They are intentionally declared here rather than in a second
             * UnityPerMaterial constant buffer. A second material constant
             * buffer would conflict with URP's LitInput layout.
             */
            half4 _PaletteColor0;
            half4 _PaletteColor1;
            half4 _PaletteColor2;
            half4 _PaletteColor3;
            half4 _PaletteColor4;
            half4 _PaletteColor5;
            half4 _PaletteColor6;

            /*
             * Per-renderer value supplied through MaterialPropertyBlock.
             *
             * It is not declared in the Properties block because it should not
             * be serialized on the material.
             */
            int _PaletteIndex;

            half4 GetPaletteColor()
            {
                int index = clamp(_PaletteIndex, 0, 6);

                if (index == 0)
                    return _PaletteColor0;

                if (index == 1)
                    return _PaletteColor1;

                if (index == 2)
                    return _PaletteColor2;

                if (index == 3)
                    return _PaletteColor3;

                if (index == 4)
                    return _PaletteColor4;

                if (index == 5)
                    return _PaletteColor5;

                return _PaletteColor6;
            }

            void PaletteLitPassFragment(
                Varyings input,
                out half4 outColor : SV_Target0)
            {
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(input);

                SurfaceData surfaceData;
                InitializeStandardLitSurfaceData(input.uv, surfaceData);

                half4 baseSample = SampleAlbedoAlpha(
                    input.uv,
                    TEXTURE2D_ARGS(_BaseMap, sampler_BaseMap)
                );

                half4 paletteColor = GetPaletteColor();

                /*
                 * Use the base texture as surface detail and the selected
                 * palette entry as the albedo tint.
                 *
                 * _BaseColor.rgb is deliberately replaced by paletteColor.rgb.
                 * Alpha behavior remains controlled by the regular Lit input.
                 */
                surfaceData.albedo =
                    baseSample.rgb *
                    paletteColor.rgb;

                surfaceData.albedo = AlphaModulate(
                    surfaceData.albedo,
                    surfaceData.alpha
                );

                InputData inputData;
                InitializeInputData(
                    input,
                    surfaceData.normalTS,
                    inputData
                );

                SETUP_DEBUG_TEXTURE_DATA(
                    inputData,
                    input.uv,
                    _BaseMap
                );

                half4 color = UniversalFragmentPBR(
                    inputData,
                    surfaceData
                );

                color.rgb = MixFog(
                    color.rgb,
                    inputData.fogCoord
                );

                color.a = OutputAlpha(
                    color.a,
                    IsSurfaceTypeTransparent(_Surface)
                );

                outColor = color;
            }

            ENDHLSL
        }

        UsePass "Universal Render Pipeline/Lit/ShadowCaster"
        UsePass "Universal Render Pipeline/Lit/GBuffer"
        UsePass "Universal Render Pipeline/Lit/DepthOnly"
        UsePass "Universal Render Pipeline/Lit/DepthNormals"
        UsePass "Universal Render Pipeline/Lit/Meta"
        UsePass "Universal Render Pipeline/Lit/Universal2D"
    }

    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}