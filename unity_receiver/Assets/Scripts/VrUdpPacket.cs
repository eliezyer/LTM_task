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
    }

    public struct VrUdpPacket
    {
        public const int PacketSizeBytes = 16;

        public uint Sequence;
        public float PositionCm;
        public byte SceneId;
        public VrFlags Flags;

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
            };
            return true;
        }
    }
}
