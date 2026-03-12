using System.Collections.Generic;
using UnityEngine;

namespace LtmVr
{
    [System.Serializable]
    public class ContextStyle
    {
        public string label = "Context";
        public Color floorColor = Color.gray;
        public Color wallColor = Color.gray;
        public PrimitiveType cuePrimitive = PrimitiveType.Cube;
        public Color cueColor = Color.white;
        public float cueSpacingCm = 20.0f;
        public Vector3 cueScaleMeters = new Vector3(0.08f, 0.20f, 0.08f);
    }

    public class VrContextGenerator : MonoBehaviour
    {
        [Header("Track Dimensions (cm)")]
        public float openingLengthCm = 60.0f;
        public float contextLengthCm = 120.0f;
        public float corridorWidthCm = 40.0f;
        public float wallHeightCm = 30.0f;

        [Header("Generation")]
        public bool regenerateOnStart = true;
        public Material materialTemplate;

        [Header("Context Styles")]
        public ContextStyle openingStyle = new ContextStyle
        {
            label = "Opening",
            floorColor = new Color(0.25f, 0.25f, 0.25f),
            wallColor = new Color(0.20f, 0.20f, 0.20f),
            cuePrimitive = PrimitiveType.Cube,
            cueColor = new Color(0.45f, 0.45f, 0.45f),
            cueSpacingCm = 25.0f,
        };

        public ContextStyle context1Style = new ContextStyle
        {
            label = "Context1",
            floorColor = new Color(0.50f, 0.15f, 0.15f),
            wallColor = new Color(0.40f, 0.10f, 0.10f),
            cuePrimitive = PrimitiveType.Cylinder,
            cueColor = new Color(0.95f, 0.80f, 0.80f),
            cueSpacingCm = 18.0f,
        };

        public ContextStyle context2Style = new ContextStyle
        {
            label = "Context2",
            floorColor = new Color(0.14f, 0.30f, 0.15f),
            wallColor = new Color(0.08f, 0.22f, 0.10f),
            cuePrimitive = PrimitiveType.Sphere,
            cueColor = new Color(0.80f, 0.95f, 0.75f),
            cueSpacingCm = 20.0f,
        };

        public ContextStyle context3Style = new ContextStyle
        {
            label = "Context3",
            floorColor = new Color(0.10f, 0.20f, 0.45f),
            wallColor = new Color(0.08f, 0.12f, 0.35f),
            cuePrimitive = PrimitiveType.Capsule,
            cueColor = new Color(0.75f, 0.85f, 0.95f),
            cueSpacingCm = 22.0f,
        };

        private readonly Dictionary<int, Transform> _sceneRoots = new Dictionary<int, Transform>();
        private Transform _itiRoot;

        private void Start()
        {
            if (regenerateOnStart)
            {
                BuildContexts();
            }
        }

        [ContextMenu("Build Contexts")]
        public void BuildContexts()
        {
            ClearChildren();
            _sceneRoots.Clear();

            _sceneRoots[0] = BuildSegment(0, openingStyle, openingLengthCm);
            _sceneRoots[1] = BuildSegment(1, context1Style, contextLengthCm);
            _sceneRoots[2] = BuildSegment(2, context2Style, contextLengthCm);
            _sceneRoots[3] = BuildSegment(3, context3Style, contextLengthCm);
            _itiRoot = BuildItiScene();
        }

        public Transform GetSceneRoot(int sceneId, bool itiActive)
        {
            if (itiActive && _itiRoot != null)
            {
                return _itiRoot;
            }

            if (_sceneRoots.TryGetValue(sceneId, out Transform root))
            {
                return root;
            }

            return _sceneRoots.ContainsKey(0) ? _sceneRoots[0] : null;
        }

        public float GetSegmentLengthMeters(int sceneId, bool itiActive)
        {
            if (itiActive)
            {
                return CmToM(openingLengthCm);
            }

            return sceneId == 0 ? CmToM(openingLengthCm) : CmToM(contextLengthCm);
        }

        public IEnumerable<Transform> GetAllSceneRoots()
        {
            foreach (KeyValuePair<int, Transform> entry in _sceneRoots)
            {
                if (entry.Value != null)
                {
                    yield return entry.Value;
                }
            }

            if (_itiRoot != null)
            {
                yield return _itiRoot;
            }
        }

        private Transform BuildSegment(int sceneId, ContextStyle style, float lengthCm)
        {
            string name = sceneId == 0 ? "Scene_Opening" : $"Scene_Context_{sceneId}";
            GameObject root = new GameObject(name);
            root.transform.SetParent(transform, false);

            float lengthM = CmToM(lengthCm);
            float widthM = CmToM(corridorWidthCm);
            float wallHeightM = CmToM(wallHeightCm);
            float wallThicknessM = 0.05f;

            CreatePrimitive(
                PrimitiveType.Cube,
                $"{name}_Floor",
                root.transform,
                new Vector3(0.0f, -0.01f, lengthM * 0.5f),
                new Vector3(widthM, 0.02f, lengthM),
                style.floorColor
            );

            CreatePrimitive(
                PrimitiveType.Cube,
                $"{name}_Wall_Left",
                root.transform,
                new Vector3(-widthM * 0.5f, wallHeightM * 0.5f, lengthM * 0.5f),
                new Vector3(wallThicknessM, wallHeightM, lengthM),
                style.wallColor
            );

            CreatePrimitive(
                PrimitiveType.Cube,
                $"{name}_Wall_Right",
                root.transform,
                new Vector3(widthM * 0.5f, wallHeightM * 0.5f, lengthM * 0.5f),
                new Vector3(wallThicknessM, wallHeightM, lengthM),
                style.wallColor
            );

            float cueSpacingM = Mathf.Max(0.08f, CmToM(style.cueSpacingCm));
            float cueY = style.cueScaleMeters.y * 0.5f;
            for (float z = cueSpacingM; z < lengthM; z += cueSpacingM)
            {
                CreatePrimitive(
                    style.cuePrimitive,
                    $"{name}_Cue_L_{z:F2}",
                    root.transform,
                    new Vector3(-widthM * 0.30f, cueY, z),
                    style.cueScaleMeters,
                    style.cueColor
                );

                CreatePrimitive(
                    style.cuePrimitive,
                    $"{name}_Cue_R_{z:F2}",
                    root.transform,
                    new Vector3(widthM * 0.30f, cueY, z),
                    style.cueScaleMeters,
                    style.cueColor
                );
            }

            return root.transform;
        }

        private Transform BuildItiScene()
        {
            GameObject root = new GameObject("Scene_ITI");
            root.transform.SetParent(transform, false);

            float lengthM = CmToM(openingLengthCm);
            float widthM = CmToM(corridorWidthCm);

            CreatePrimitive(
                PrimitiveType.Cube,
                "Scene_ITI_Floor",
                root.transform,
                new Vector3(0.0f, -0.01f, lengthM * 0.5f),
                new Vector3(widthM, 0.02f, lengthM),
                Color.black
            );

            return root.transform;
        }

        private void CreatePrimitive(
            PrimitiveType primitiveType,
            string objectName,
            Transform parent,
            Vector3 localPosition,
            Vector3 localScale,
            Color color)
        {
            GameObject go = GameObject.CreatePrimitive(primitiveType);
            go.name = objectName;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            go.transform.localScale = localScale;

            Renderer renderer = go.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.sharedMaterial = BuildMaterial(color);
            }
        }

        private Material BuildMaterial(Color color)
        {
            Material material;
            if (materialTemplate != null)
            {
                material = new Material(materialTemplate);
            }
            else
            {
                Shader shader = Shader.Find("Standard");
                if (shader == null)
                {
                    shader = Shader.Find("Universal Render Pipeline/Lit");
                }
                if (shader == null)
                {
                    shader = Shader.Find("Sprites/Default");
                }
                if (shader == null)
                {
                    throw new System.InvalidOperationException("No compatible shader found for generated context materials.");
                }
                material = new Material(shader);
            }

            material.color = color;
            return material;
        }

        private void ClearChildren()
        {
            List<GameObject> toDestroy = new List<GameObject>();
            for (int i = 0; i < transform.childCount; i++)
            {
                toDestroy.Add(transform.GetChild(i).gameObject);
            }

            for (int i = 0; i < toDestroy.Count; i++)
            {
#if UNITY_EDITOR
                if (!Application.isPlaying)
                {
                    DestroyImmediate(toDestroy[i]);
                    continue;
                }
#endif
                Destroy(toDestroy[i]);
            }
        }

        private static float CmToM(float cm)
        {
            return cm * 0.01f;
        }
    }
}
