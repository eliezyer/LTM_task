using UnityEngine;

namespace LtmVr
{
    public class VrRenderController : MonoBehaviour
    {
        [Header("Dependencies")]
        public VrUdpReceiver udpReceiver;
        public VrContextGenerator contextGenerator;
        public Transform rigTransform;

        [Header("Behavior")]
        public bool consumePackets = true;
        public bool clampPositionToSegment = true;

        private int _activeSceneId = -1;
        private bool _activeIti;
        private bool _initialized;

        private void Reset()
        {
            udpReceiver = FindObjectOfType<VrUdpReceiver>();
            contextGenerator = FindObjectOfType<VrContextGenerator>();
            if (Camera.main != null)
            {
                rigTransform = Camera.main.transform;
            }
        }

        private void Start()
        {
            if (contextGenerator != null)
            {
                contextGenerator.BuildContexts();
            }
            ActivateScene(0, false);
            _initialized = true;
        }

        private void Update()
        {
            if (udpReceiver == null || contextGenerator == null)
            {
                return;
            }

            VrUdpPacket packet;
            bool hasPacket = consumePackets
                ? udpReceiver.TryConsumeLatest(out packet)
                : udpReceiver.TryPeekLatest(out packet);

            if (!hasPacket)
            {
                return;
            }

            bool itiActive = (packet.Flags & VrFlags.ItiActive) != 0;
            bool teleport = (packet.Flags & VrFlags.Teleport) != 0;

            if (!_initialized || teleport || packet.SceneId != _activeSceneId || itiActive != _activeIti)
            {
                ActivateScene(packet.SceneId, itiActive);
            }

            ApplyPosition(packet.PositionCm, packet.SceneId, itiActive);
        }

        private void ActivateScene(int sceneId, bool itiActive)
        {
            foreach (Transform root in contextGenerator.GetAllSceneRoots())
            {
                root.gameObject.SetActive(false);
            }

            Transform activeRoot = contextGenerator.GetSceneRoot(sceneId, itiActive);
            if (activeRoot != null)
            {
                activeRoot.gameObject.SetActive(true);
            }

            _activeSceneId = sceneId;
            _activeIti = itiActive;
            _initialized = true;
        }

        private void ApplyPosition(float positionCm, int sceneId, bool itiActive)
        {
            if (rigTransform == null)
            {
                return;
            }

            float zMeters = positionCm * 0.01f;
            if (clampPositionToSegment)
            {
                float maxZ = contextGenerator.GetSegmentLengthMeters(sceneId, itiActive);
                zMeters = Mathf.Clamp(zMeters, 0.0f, maxZ);
            }

            Vector3 position = rigTransform.localPosition;
            position.z = zMeters;
            rigTransform.localPosition = position;
        }
    }
}
