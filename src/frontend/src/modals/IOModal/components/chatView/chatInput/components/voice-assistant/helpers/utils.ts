export function base64ToFloat32Array(base64String: string): Float32Array {
  const binaryString = atob(base64String);
  const pcmData = new Int16Array(binaryString.length / 2);

  for (let i = 0; i < binaryString.length; i += 2) {
    const lsb = binaryString.charCodeAt(i);
    const msb = binaryString.charCodeAt(i + 1);
    pcmData[i / 2] = (msb << 8) | lsb;
  }

  const float32Data = new Float32Array(pcmData.length);
  for (let i = 0; i < pcmData.length; i++) {
    float32Data[i] = pcmData[i] / 32768.0;
  }

  return float32Data;
}
