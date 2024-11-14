import { useState, useRef, useEffect } from "react";
import { Button } from "../ui/button";
import { Mic, MicOff } from "lucide-react";
import { workletCode } from "./streamProcessor";
import { base64ToFloat32Array } from "./utils";

interface VoiceAssistantProps {
  flowId: string;
}

export function VoiceAssistant({ flowId }: VoiceAssistantProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("");
  const [message, setMessage] = useState("");
  
  const audioContextRef = useRef<AudioContext | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const processorRef = useRef<AudioWorkletNode | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Initialize audio context and websocket
  const initializeAudio = async () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || 
          (window as any).webkitAudioContext)({
          sampleRate: 24000
        });
      }
      
      await audioContextRef.current.resume();
      startConversation();
    } catch (error) {
      console.error('Failed to initialize audio:', error);
      setStatus('Error: Failed to initialize audio');
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!audioContextRef.current) return;

      microphoneRef.current = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      microphoneRef.current.connect(analyserRef.current);

      const blob = new Blob([workletCode], { type: 'application/javascript' });
      const workletUrl = URL.createObjectURL(blob);

      try {
        await audioContextRef.current.audioWorklet.addModule(workletUrl);
        processorRef.current = new AudioWorkletNode(audioContextRef.current, 'stream_processor');

        analyserRef.current.connect(processorRef.current);
        processorRef.current.connect(audioContextRef.current.destination);

        processorRef.current.port.onmessage = (event) => {
          if (event.data.type === 'input' && event.data.audio && wsRef.current) {
            const base64Audio = btoa(String.fromCharCode.apply(null, 
              Array.from(new Uint8Array(event.data.audio.buffer))));
            
            wsRef.current.send(JSON.stringify({
              type: 'input_audio_buffer.append',
              audio: base64Audio
            }));
          } else if (event.data.type === 'done') {
            if (audioQueueRef.current.length > 0) {
              playNextAudioChunk();
            } else {
              isPlayingRef.current = false;
            }
          }
        };

        setIsRecording(true);
      } catch (err) {
        console.error('AudioWorklet failed to load:', err);
        throw err;
      } finally {
        URL.revokeObjectURL(workletUrl);
      }

    } catch (err) {
      console.error('Error accessing microphone:', err);
      setStatus('Error: ' + (err as Error).message);
    }
  };

  const stopRecording = () => {
    if (microphoneRef.current) {
      microphoneRef.current.disconnect();
      microphoneRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsRecording(false);
  };

  const playNextAudioChunk = () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      return;
    }

    isPlayingRef.current = true;
    const audioBuffer = audioQueueRef.current.shift();

    if (audioBuffer && processorRef.current) {
      try {
        processorRef.current.port.postMessage({
          type: 'playback',
          audio: audioBuffer.getChannelData(0)
        });
      } catch (error) {
        console.error('Error playing audio:', error);
        isPlayingRef.current = false;
      }
    }
  };

  const handleWebSocketMessage = (event: MessageEvent) => {
    const data = JSON.parse(event.data);
    
    switch (data.type) {
      case 'response.content_part.added':
        if (data.part?.type === 'text' && data.part.text) {
          setMessage(prev => prev + data.part.text);
        }
        break;

      case 'response.audio.delta':
        if (data.delta && audioContextRef.current) {
          try {
            const float32Data = base64ToFloat32Array(data.delta);
            const audioBuffer = audioContextRef.current.createBuffer(
              2,
              float32Data.length,
              24000
            );

            audioBuffer.copyToChannel(float32Data, 0);
            audioBuffer.copyToChannel(float32Data, 1);

            audioQueueRef.current.push(audioBuffer);

            if (!isPlayingRef.current) {
              playNextAudioChunk();
            }
          } catch (error) {
            console.error('Error processing audio response:', error);
          }
        }
        break;

      case 'error':
        console.error('Server error:', data.error);
        setStatus('Error: ' + data.error);
        break;
    }
  };

  const startConversation = () => {
    try {
      wsRef.current = new WebSocket(
        `ws://localhost:7860/api/v1/voice/ws/${flowId}`
      );

      wsRef.current.onopen = () => {
        setStatus('Connected');
        startRecording();
      };

      wsRef.current.onmessage = handleWebSocketMessage;

      wsRef.current.onclose = (event) => {
        setStatus(`Disconnected (${event.code})`);
        stopRecording();
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket Error:', error);
        setStatus('Connection error');
      };
      
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setStatus('Connection failed');
    }
  };

  const toggleRecording = () => {
    if (!isRecording) {
      initializeAudio();
    } else {
      stopRecording();
    }
    setIsRecording(!isRecording);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  return (
    <div className="flex flex-col items-center gap-2">
      <Button
        variant={isRecording ? "destructive" : "default"}
        onClick={toggleRecording}
        className="gap-2"
      >
        {isRecording ? <MicOff size={16} /> : <Mic size={16} />}
        {isRecording ? "Stop" : "Start"} Voice Assistant
      </Button>
      {status && <div className="text-sm text-gray-600">{status}</div>}
      {message && <div className="text-sm">{message}</div>}
    </div>
  );
} 