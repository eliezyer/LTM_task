using System;

namespace LtmVr
{
    [Flags]
    public enum VrFlags : byte
    {
        None = 0,
        Teleport = 1 << 0,
        ItiActive = 1 << 1,
        Freeze = 1 << 2,
        OutcomeActive = 1 << 3,
        HabituationActive = 1 << 4,
    }

    public struct VrUdpPacket
    {
        public const int PacketSizeBytes = 16;

        public uint Sequence;
        public float PositionCm;
        public byte SceneId;
        public VrFlags Flags;
        public ushort OpeningLengthCm;
        public ushort ContextLengthCm;
        public ushort OutcomeLengthCm;

        public bool HasTrackDimensions
        {
            get
            {
                return OpeningLengthCm > 0
                    && ContextLengthCm > 0
                    && OutcomeLengthCm > 0;
            }
        }

        public static bool TryParse(byte[] data, int length, out VrUdpPacket packet)
        {
            packet = default;
            if (data == null || length < PacketSizeBytes)
            {
                return false;
            }

            uint seq = (uint)(
                data[0] |
                (data[1] << 8) |
                (data[2] << 16) |
                (data[3] << 24));

            float positionCm;
            if (BitConverter.IsLittleEndian)
            {
                positionCm = BitConverter.ToSingle(data, 4);
            }
            else
            {
                byte[] tmp = new byte[4];
                Array.Copy(data, 4, tmp, 0, 4);
                Array.Reverse(tmp);
                positionCm = BitConverter.ToSingle(tmp, 0);
            }

            packet = new VrUdpPacket
            {
                Sequence = seq,
                PositionCm = positionCm,
                SceneId = data[8],
                Flags = (VrFlags)data[9],
                OpeningLengthCm = ReadUInt16LittleEndian(data, 10),
                ContextLengthCm = ReadUInt16LittleEndian(data, 12),
                OutcomeLengthCm = ReadUInt16LittleEndian(data, 14),
            };
            return true;
        }

        private static ushort ReadUInt16LittleEndian(byte[] data, int offset)
        {
            return (ushort)(data[offset] | (data[offset + 1] << 8));
        }
    }
}
