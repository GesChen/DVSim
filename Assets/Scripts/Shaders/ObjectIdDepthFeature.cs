using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public sealed class ObjectIdDepthFeature : ScriptableRendererFeature {
	[SerializeField]
	private Shader shader;

	private Material material;
	private ObjectIdDepthPass pass;

	public override void Create() {
		material = CoreUtils.CreateEngineMaterial(shader);
		pass = new ObjectIdDepthPass(material) {
			renderPassEvent = RenderPassEvent.AfterRenderingOpaques
		};
	}

	public override void AddRenderPasses(
		ScriptableRenderer renderer,
		ref RenderingData renderingData) {
		pass.SetCameraDepthTarget(renderer.cameraDepthTargetHandle);
		renderer.EnqueuePass(pass);
	}

	protected override void Dispose(bool disposing) {
		CoreUtils.Destroy(material);
	}

	private sealed class ObjectIdDepthPass : ScriptableRenderPass {
		private readonly Material material;

		private RTHandle idTexture;
		private RTHandle depthTexture;
		private RTHandle depthBuffer;

		private readonly RTHandle[] colorAttachments = new RTHandle[2];

		private readonly ShaderTagId shaderTagId =
			new ShaderTagId("UniversalForward");

		private FilteringSettings filteringSettings =
			new FilteringSettings(RenderQueueRange.opaque);

		public ObjectIdDepthPass(Material material) {
			this.material = material;
		}

		public void SetCameraDepthTarget(RTHandle cameraDepthTarget) {
			depthBuffer = cameraDepthTarget;
		}

		public override void OnCameraSetup(
			CommandBuffer cmd,
			ref RenderingData renderingData) {
			RenderTextureDescriptor descriptor =
				renderingData.cameraData.cameraTargetDescriptor;

			descriptor.msaaSamples = 1;
			descriptor.depthBufferBits = 0;

			descriptor.graphicsFormat = GraphicsFormat.R32_UInt;

			RenderingUtils.ReAllocateIfNeeded(
				ref idTexture,
				descriptor,
				FilterMode.Point,
				TextureWrapMode.Clamp,
				name: "_ObjectIdTexture");

			descriptor.graphicsFormat = GraphicsFormat.R32_SFloat;

			RenderingUtils.ReAllocateIfNeeded(
				ref depthTexture,
				descriptor,
				FilterMode.Point,
				TextureWrapMode.Clamp,
				name: "_ObjectLinearDepthTexture");

			colorAttachments[0] = idTexture;
			colorAttachments[1] = depthTexture;

			ConfigureTarget(colorAttachments, depthBuffer);

			ConfigureClear(
				ClearFlag.Color,
				Color.clear);
		}

		public override void Execute(
			ScriptableRenderContext context,
			ref RenderingData renderingData) {
			CommandBuffer cmd =
				CommandBufferPool.Get("Object ID and Depth");

			using (new ProfilingScope(
					   cmd,
					   new ProfilingSampler("Object ID and Depth"))) {
				context.ExecuteCommandBuffer(cmd);
				cmd.Clear();

				SortingCriteria sortingCriteria =
					renderingData.cameraData.defaultOpaqueSortFlags;

				DrawingSettings drawingSettings =
					CreateDrawingSettings(
						shaderTagId,
						ref renderingData,
						sortingCriteria);

				drawingSettings.overrideMaterial = material;
				drawingSettings.overrideMaterialPassIndex = 0;

				context.DrawRenderers(
					renderingData.cullResults,
					ref drawingSettings,
					ref filteringSettings);

				cmd.SetGlobalTexture(
					"_ObjectIdTexture",
					idTexture);

				cmd.SetGlobalTexture(
					"_ObjectLinearDepthTexture",
					depthTexture);
			}

			context.ExecuteCommandBuffer(cmd);
			CommandBufferPool.Release(cmd);
		}

		public override void OnCameraCleanup(CommandBuffer cmd) {
		}

		public void Dispose() {
			idTexture?.Release();
			depthTexture?.Release();
		}
	}
}