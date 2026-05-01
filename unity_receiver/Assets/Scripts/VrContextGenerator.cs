using System.Collections.Generic;
using UnityEngine;

namespace LtmVr
{
    public enum ContextWallPattern
    {
        Solid,
        VerticalGratings,
        HorizontalGratings,
        Checkerboard,
        PolkaDots,
        Diamonds,
    }

    [System.Serializable]
    public class ContextStyle
    {
        [HideInInspector]
        public int styleVersion = 0;

        public string label = "Context";
        public ContextWallPattern wallPattern = ContextWallPattern.VerticalGratings;

        public float patternScaleCm = 10.0f;

        [Range(0.05f, 0.95f)]
        public float patternDutyCycle = 0.5f;

        [Range(0.05f, 0.48f)]
        public float featureRadiusFraction = 0.32f;

        [Range(0.05f, 1.0f)]
        public float blueIntensity = 1.0f;

        public bool invertPattern = false;
    }

    public class VrContextGenerator : MonoBehaviour
    {
        private const int CurrentContextStyleVersion = 2;

        [Header("Track Dimensions (cm)")]
        public float openingLengthCm = 60.0f;
        public float contextLengthCm = 120.0f;
        public float corridorWidthCm = 40.0f;
        public float wallHeightCm = 30.0f;

        [Header("Generation")]
        public bool regenerateOnStart = true;
        public bool forceBlackWorldSettings = true;
        public bool useMaterialTemplateShader = false;

        [Tooltip("Optional shader source. Keep disabled/empty unless you know this shader is compatible with your render pipeline.")]
        public Material materialTemplate;

        public int patternTexturePixels = 256;

        [Header("Context Styles")]
        public ContextStyle openingStyle = CreateOpeningStyle();
        public ContextStyle context1Style = CreateContext1Style();
        public ContextStyle context2Style = CreateContext2Style();
        public ContextStyle context3Style = CreateContext3Style();

        private readonly Dictionary<int, Transform> _sceneRoots = new Dictionary<int, Transform>();
        private readonly List<Material> _generatedMaterials = new List<Material>();
        private readonly List<Texture2D> _generatedTextures = new List<Texture2D>();

        private Transform _itiRoot;
        private Shader _contextShader;
        private bool _warnedAboutTemplateShader;

        private void Start()
        {
            if (forceBlackWorldSettings)
            {
                ApplyBlackWorldSettings();
            }

            if (regenerateOnStart)
            {
                BuildContexts();
            }
        }

        private void OnDestroy()
        {
            ClearGeneratedAssets();
        }

        [ContextMenu("Build Contexts")]
        public void BuildContexts()
        {
            if (forceBlackWorldSettings)
            {
                ApplyBlackWorldSettings();
            }

            ClearChildren();
            ClearGeneratedAssets();
            UpgradeLegacyStyles();
            _sceneRoots.Clear();

            _sceneRoots[0] = BuildSegment(0, openingStyle, openingLengthCm);
            _sceneRoots[1] = BuildSegment(1, context1Style, contextLengthCm);
            _sceneRoots[2] = BuildSegment(2, context2Style, contextLengthCm);
            _sceneRoots[3] = BuildSegment(3, context3Style, contextLengthCm);
            _itiRoot = BuildItiScene();
        }

        private void UpgradeLegacyStyles()
        {
            UpgradeLegacyStyle(ref openingStyle, CreateOpeningStyle());
            UpgradeLegacyStyle(ref context1Style, CreateContext1Style());
            UpgradeLegacyStyle(ref context2Style, CreateContext2Style());
            UpgradeLegacyStyle(ref context3Style, CreateContext3Style());
        }

        private static void UpgradeLegacyStyle(ref ContextStyle style, ContextStyle defaultStyle)
        {
            if (style == null || style.styleVersion < CurrentContextStyleVersion)
            {
                style = defaultStyle;
            }
        }

        private static ContextStyle CreateOpeningStyle()
        {
            return new ContextStyle
            {
                styleVersion = CurrentContextStyleVersion,
                label = "Opening",
                wallPattern = ContextWallPattern.Diamonds,
                patternScaleCm = 14.0f,
                patternDutyCycle = 0.5f,
                featureRadiusFraction = 0.42f,
                blueIntensity = 1.0f,
            };
        }

        private static ContextStyle CreateContext1Style()
        {
            return new ContextStyle
            {
                styleVersion = CurrentContextStyleVersion,
                label = "Context1_Gratings",
                wallPattern = ContextWallPattern.VerticalGratings,
                patternScaleCm = 8.0f,
                patternDutyCycle = 0.35f,
                featureRadiusFraction = 0.32f,
                blueIntensity = 1.0f,
            };
        }

        private static ContextStyle CreateContext2Style()
        {
            return new ContextStyle
            {
                styleVersion = CurrentContextStyleVersion,
                label = "Context2_Checkers",
                wallPattern = ContextWallPattern.Checkerboard,
                patternScaleCm = 10.0f,
                patternDutyCycle = 0.5f,
                featureRadiusFraction = 0.32f,
                blueIntensity = 1.0f,
            };
        }

        private static ContextStyle CreateContext3Style()
        {
            return new ContextStyle
            {
                styleVersion = CurrentContextStyleVersion,
                label = "Context3_PolkaDots",
                wallPattern = ContextWallPattern.PolkaDots,
                patternScaleCm = 12.0f,
                patternDutyCycle = 0.5f,
                featureRadiusFraction = 0.28f,
                blueIntensity = 1.0f,
            };
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

            Material blackMaterial = BuildSolidMaterial(Color.black);
            Material wallMaterial = BuildPatternMaterial(style, lengthM, wallHeightM);

            CreatePrimitive(
                PrimitiveType.Cube,
                $"{name}_Floor",
                root.transform,
                new Vector3(0.0f, -0.01f, lengthM * 0.5f),
                new Vector3(widthM, 0.02f, lengthM),
                blackMaterial
            );

            CreatePrimitive(
                PrimitiveType.Cube,
                $"{name}_Wall_Left_{style.label}",
                root.transform,
                new Vector3(-widthM * 0.5f, wallHeightM * 0.5f, lengthM * 0.5f),
                new Vector3(wallThicknessM, wallHeightM, lengthM),
                wallMaterial
            );

            CreatePrimitive(
                PrimitiveType.Cube,
                $"{name}_Wall_Right_{style.label}",
                root.transform,
                new Vector3(widthM * 0.5f, wallHeightM * 0.5f, lengthM * 0.5f),
                new Vector3(wallThicknessM, wallHeightM, lengthM),
                wallMaterial
            );

            return root.transform;
        }

        private Transform BuildItiScene()
        {
            GameObject root = new GameObject("Scene_ITI");
            root.transform.SetParent(transform, false);

            float lengthM = CmToM(openingLengthCm);
            float widthM = CmToM(corridorWidthCm);
            Material blackMaterial = BuildSolidMaterial(Color.black);

            CreatePrimitive(
                PrimitiveType.Cube,
                "Scene_ITI_Floor",
                root.transform,
                new Vector3(0.0f, -0.01f, lengthM * 0.5f),
                new Vector3(widthM, 0.02f, lengthM),
                blackMaterial
            );

            return root.transform;
        }

        private void CreatePrimitive(
            PrimitiveType primitiveType,
            string objectName,
            Transform parent,
            Vector3 localPosition,
            Vector3 localScale,
            Material material)
        {
            GameObject go = GameObject.CreatePrimitive(primitiveType);
            go.name = objectName;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            go.transform.localScale = localScale;

            Renderer renderer = go.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.sharedMaterial = material;
            }
        }

        private Material BuildSolidMaterial(Color color)
        {
            Texture2D texture = BuildSolidTexture(color);
            return BuildMaterial(color, texture, Vector2.one);
        }

        private Material BuildPatternMaterial(ContextStyle style, float lengthM, float wallHeightM)
        {
            Texture2D texture = BuildPatternTexture(style);
            float featureSizeM = Mathf.Max(0.01f, CmToM(style.patternScaleCm));
            float tileSizeM = style.wallPattern == ContextWallPattern.Checkerboard
                ? featureSizeM * 2.0f
                : featureSizeM;

            Vector2 textureScale = new Vector2(
                Mathf.Max(1.0f, lengthM / tileSizeM),
                Mathf.Max(1.0f, wallHeightM / tileSizeM)
            );

            return BuildMaterial(Blue(style.blueIntensity), texture, textureScale);
        }

        private Material BuildMaterial(Color color, Texture2D texture, Vector2 textureScale)
        {
            Material material = new Material(GetContextShader())
            {
                name = texture == null ? "Generated_Black_Unlit" : $"Generated_{texture.name}_Unlit",
                hideFlags = HideFlags.DontSave,
            };

            ConfigureMaterial(material, color, texture, textureScale);
            _generatedMaterials.Add(material);
            return material;
        }

        private void ConfigureMaterial(Material material, Color color, Texture2D texture, Vector2 textureScale)
        {
            SetColorIfPresent(material, "_Color", color);
            SetColorIfPresent(material, "_BaseColor", color);
            SetColorIfPresent(material, "_UnlitColor", color);
            SetColorIfPresent(material, "_EmissionColor", Color.black);
            SetColorIfPresent(material, "_SpecColor", Color.black);

            SetTextureIfPresent(material, "_MainTex", texture, textureScale);
            SetTextureIfPresent(material, "_BaseMap", texture, textureScale);
            SetTextureIfPresent(material, "_BaseColorMap", texture, textureScale);
            SetTextureIfPresent(material, "_UnlitColorMap", texture, textureScale);

            SetFloatIfPresent(material, "_Metallic", 0.0f);
            SetFloatIfPresent(material, "_Glossiness", 0.0f);
            SetFloatIfPresent(material, "_Smoothness", 0.0f);
        }

        private Texture2D BuildPatternTexture(ContextStyle style)
        {
            int size = Mathf.Clamp(patternTexturePixels, 16, 1024);
            Texture2D texture = new Texture2D(size, size, TextureFormat.RGBA32, false)
            {
                name = SanitizeTextureName(style),
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Repeat,
                hideFlags = HideFlags.DontSave,
            };

            Color blue = Blue(style.blueIntensity);
            Color black = Color.black;
            Color[] pixels = new Color[size * size];

            for (int y = 0; y < size; y++)
            {
                float v = (y + 0.5f) / size;
                for (int x = 0; x < size; x++)
                {
                    float u = (x + 0.5f) / size;
                    bool isBlue = IsPatternBlue(style, u, v);
                    pixels[y * size + x] = isBlue ? blue : black;
                }
            }

            texture.SetPixels(pixels);
            texture.Apply(false, true);
            _generatedTextures.Add(texture);
            return texture;
        }

        private Texture2D BuildSolidTexture(Color color)
        {
            Texture2D texture = new Texture2D(1, 1, TextureFormat.RGBA32, false)
            {
                name = color == Color.black ? "Solid_Black" : "Solid_Blue",
                filterMode = FilterMode.Point,
                wrapMode = TextureWrapMode.Repeat,
                hideFlags = HideFlags.DontSave,
            };

            texture.SetPixel(0, 0, color);
            texture.Apply(false, true);
            _generatedTextures.Add(texture);
            return texture;
        }

        private static bool IsPatternBlue(ContextStyle style, float u, float v)
        {
            float duty = Mathf.Clamp(style.patternDutyCycle, 0.05f, 0.95f);
            float radius = Mathf.Clamp(style.featureRadiusFraction, 0.05f, 0.48f);
            bool isBlue;

            switch (style.wallPattern)
            {
                case ContextWallPattern.Solid:
                    isBlue = true;
                    break;
                case ContextWallPattern.VerticalGratings:
                    isBlue = u < duty;
                    break;
                case ContextWallPattern.HorizontalGratings:
                    isBlue = v < duty;
                    break;
                case ContextWallPattern.Checkerboard:
                    isBlue = (((int)(u * 2.0f) + (int)(v * 2.0f)) % 2) == 0;
                    break;
                case ContextWallPattern.PolkaDots:
                    isBlue = Vector2.Distance(new Vector2(u, v), new Vector2(0.5f, 0.5f)) <= radius;
                    break;
                case ContextWallPattern.Diamonds:
                    isBlue = Mathf.Abs(u - 0.5f) + Mathf.Abs(v - 0.5f) <= radius;
                    break;
                default:
                    isBlue = false;
                    break;
            }

            return style.invertPattern ? !isBlue : isBlue;
        }

        private Shader GetContextShader()
        {
            if (IsUsableShader(_contextShader))
            {
                return _contextShader;
            }

            if (useMaterialTemplateShader && materialTemplate != null && IsUsableShader(materialTemplate.shader))
            {
                _contextShader = materialTemplate.shader;
                return _contextShader;
            }

            if (useMaterialTemplateShader && materialTemplate != null && !_warnedAboutTemplateShader)
            {
                Debug.LogWarning("[VrContextGenerator] Material Template shader is missing or unsupported. Using a generated unlit material instead.");
                _warnedAboutTemplateShader = true;
            }

            string[] shaderNames =
            {
                "Universal Render Pipeline/Unlit",
                "HDRP/Unlit",
                "High Definition Render Pipeline/Unlit",
                "Unlit/Texture",
                "Sprites/Default",
                "Universal Render Pipeline/Lit",
                "Standard",
            };

            for (int i = 0; i < shaderNames.Length; i++)
            {
                Shader shader = Shader.Find(shaderNames[i]);
                if (IsUsableShader(shader))
                {
                    _contextShader = shader;
                    return _contextShader;
                }
            }

            throw new System.InvalidOperationException("No compatible shader found for generated context materials.");
        }

        private static bool IsUsableShader(Shader shader)
        {
            return shader != null
                && shader.isSupported
                && shader.name != "Hidden/InternalErrorShader";
        }

        private static void SetColorIfPresent(Material material, string propertyName, Color color)
        {
            if (material.HasProperty(propertyName))
            {
                material.SetColor(propertyName, color);
            }
        }

        private static void SetFloatIfPresent(Material material, string propertyName, float value)
        {
            if (material.HasProperty(propertyName))
            {
                material.SetFloat(propertyName, value);
            }
        }

        private static void SetTextureIfPresent(Material material, string propertyName, Texture texture, Vector2 textureScale)
        {
            if (!material.HasProperty(propertyName))
            {
                return;
            }

            material.SetTexture(propertyName, texture);
            if (texture != null)
            {
                material.SetTextureScale(propertyName, textureScale);
            }
        }

        private void ApplyBlackWorldSettings()
        {
            RenderSettings.skybox = null;
            RenderSettings.ambientLight = Color.black;

            Camera[] cameras = Camera.allCameras;
            for (int i = 0; i < cameras.Length; i++)
            {
                cameras[i].clearFlags = CameraClearFlags.SolidColor;
                cameras[i].backgroundColor = Color.black;
            }
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
                DestroyUnityObject(toDestroy[i]);
            }
        }

        private void ClearGeneratedAssets()
        {
            for (int i = 0; i < _generatedMaterials.Count; i++)
            {
                DestroyUnityObject(_generatedMaterials[i]);
            }
            _generatedMaterials.Clear();

            for (int i = 0; i < _generatedTextures.Count; i++)
            {
                DestroyUnityObject(_generatedTextures[i]);
            }
            _generatedTextures.Clear();
        }

        private static void DestroyUnityObject(UnityEngine.Object unityObject)
        {
            if (unityObject == null)
            {
                return;
            }

#if UNITY_EDITOR
            if (!Application.isPlaying)
            {
                UnityEngine.Object.DestroyImmediate(unityObject);
                return;
            }
#endif
            UnityEngine.Object.Destroy(unityObject);
        }

        private static string SanitizeTextureName(ContextStyle style)
        {
            string label = string.IsNullOrEmpty(style.label) ? "Context" : style.label.Replace(" ", "_");
            return $"{label}_{style.wallPattern}";
        }

        private static Color Blue(float intensity)
        {
            return new Color(0.0f, 0.0f, Mathf.Clamp01(intensity), 1.0f);
        }

        private static float CmToM(float cm)
        {
            return cm * 0.01f;
        }
    }
}
