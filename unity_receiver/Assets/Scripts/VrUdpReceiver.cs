using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

namespace LtmVr
{
    public class VrUdpReceiver : MonoBehaviour
    {
        [Header("Network")]
        public string bindAddress = "0.0.0.0";
        public int listenPort = 5005;
        public bool logPacketDrops = true;

        private readonly object _packetLock = new object();
        private UdpClient _udpClient;
        private Thread _receiveThread;
        private volatile bool _running;

        private VrUdpPacket _latestPacket;
        private bool _hasPacket;
        private uint _lastSequence;
        private bool _sequenceInitialized;

        private void OnEnable()
        {
            StartReceiver();
        }

        private void OnDisable()
        {
            StopReceiver();
        }

        private void OnApplicationQuit()
        {
            StopReceiver();
        }

        [ContextMenu("Restart UDP Receiver")]
        public void RestartReceiver()
        {
            StopReceiver();
            StartReceiver();
        }

        public bool TryConsumeLatest(out VrUdpPacket packet)
        {
            lock (_packetLock)
            {
                if (!_hasPacket)
                {
                    packet = default;
                    return false;
                }

                packet = _latestPacket;
                _hasPacket = false;
                return true;
            }
        }

        public bool TryPeekLatest(out VrUdpPacket packet)
        {
            lock (_packetLock)
            {
                if (!_hasPacket)
                {
                    packet = default;
                    return false;
                }

                packet = _latestPacket;
                return true;
            }
        }

        private void StartReceiver()
        {
            if (_running)
            {
                return;
            }

            try
            {
                IPAddress bindIp = IPAddress.Parse(bindAddress);
                _udpClient = new UdpClient(new IPEndPoint(bindIp, listenPort));
                _udpClient.Client.ReceiveTimeout = 250;

                _running = true;
                _receiveThread = new Thread(ReceiveLoop)
                {
                    IsBackground = true,
                    Name = "VrUdpReceiverThread",
                };
                _receiveThread.Start();

                Debug.Log($"[VrUdpReceiver] Listening on {bindAddress}:{listenPort}");
            }
            catch (Exception ex)
            {
                _running = false;
                Debug.LogError($"[VrUdpReceiver] Failed to start receiver: {ex}");
            }
        }

        private void StopReceiver()
        {
            _running = false;

            if (_udpClient != null)
            {
                _udpClient.Close();
                _udpClient = null;
            }

            if (_receiveThread != null && _receiveThread.IsAlive)
            {
                _receiveThread.Join(500);
                _receiveThread = null;
            }
        }

        private void ReceiveLoop()
        {
            IPEndPoint remote = new IPEndPoint(IPAddress.Any, 0);

            while (_running)
            {
                try
                {
                    byte[] data = _udpClient.Receive(ref remote);
                    if (!VrUdpPacket.TryParse(data, data.Length, out VrUdpPacket packet))
                    {
                        continue;
                    }

                    if (logPacketDrops)
                    {
                        CheckSequence(packet.Sequence);
                    }

                    lock (_packetLock)
                    {
                        _latestPacket = packet;
                        _hasPacket = true;
                    }
                }
                catch (SocketException ex)
                {
                    if (ex.SocketErrorCode == SocketError.TimedOut)
                    {
                        continue;
                    }

                    if (_running)
                    {
                        Debug.LogWarning($"[VrUdpReceiver] Socket error: {ex.SocketErrorCode}");
                    }
                }
                catch (ObjectDisposedException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    if (_running)
                    {
                        Debug.LogError($"[VrUdpReceiver] Receive loop error: {ex}");
                    }
                }
            }
        }

        private void CheckSequence(uint sequence)
        {
            if (!_sequenceInitialized)
            {
                _sequenceInitialized = true;
                _lastSequence = sequence;
                return;
            }

            uint expected = _lastSequence + 1;
            if (sequence != expected)
            {
                Debug.LogWarning($"[VrUdpReceiver] Packet drop/reorder detected. Expected {expected}, got {sequence}");
            }

            _lastSequence = sequence;
        }
    }
}
