import express, { Request, Response } from 'express';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import cors from 'cors';
import dotenv from 'dotenv';
import { GoogleGenAI } from '@google/genai';

dotenv.config();

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server });

const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Initialize Gemini API Client
const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY || '',
});

// ==========================================
// 1. REST API Endpoint: Voice & AI Processing
// ==========================================
interface CommandRequest {
  transcript: string;
  language?: string;
}

app.post('/api/cognitive/command', async (req: Request<{}, {}, CommandRequest>, res: Response) => {
  try {
    const { transcript, language = 'en' } = req.body;

    if (!transcript) {
      return res.status(400).json({ error: 'Transcript payload is required.' });
    }

    console.log(`[Acoustic Processing] Received transcript (${language}): "${transcript}"`);

    // Prompt engineered to act as the Cognitive Operating System
    const prompt = `
      You are the Cognitive Operations Core for a Robotics and Computer Vision System.
      Analyze this user command: "${transcript}"
      Language requested: ${language}

      Respond strictly in JSON with this structure:
      {
        "status": "SUCCESS",
        "assistantResponse": "Short executive response to the user in requested language",
        "vocalMetrics": {
          "calmStability": 85,
          "vocalFriction": 12,
          "processingLoad": 45
        },
        "systemAction": "ROBOTICS_NAVIGATION | VISION_SCAN | SYSTEM_IDLE | EMERGENCY_STOP",
        "telemetryImpact": {
          "cpuLoad": 65,
          "visionFps": 60,
          "taskCompletion": 92
        }
      }
    `;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
      config: {
        responseMimeType: 'application/json',
      },
    });

    const parsedData = JSON.parse(response.text || '{}');
    return res.json(parsedData);

  } catch (error) {
    console.error('[API Error]', error);
    return res.status(500).json({
      error: 'Failed to process cognitive request.',
      details: error instanceof Error ? error.message : String(error)
    });
  }
});

// ==========================================
// 2. WebSockets: Live Telemetry Streaming
// ==========================================
wss.on('connection', (ws: WebSocket) => {
  console.log('[WebSocket] Client matrix interface connected.');

  // Push telemetry metrics every 2 seconds to connected clients
  const telemetryInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      const liveMetrics = {
        type: 'TELEMETRY_UPDATE',
        timestamp: new Date().toISOString(),
        neural: {
          velocity: Math.floor(Math.random() * 20) + 80,
          index: (Math.random() * 2 + 8).toFixed(1),
          active: Math.floor(Math.random() * 10) + 90
        },
        vision: {
          fps: Math.floor(Math.random() * 15) + 45,
          accuracy: (Math.random() * 2 + 97).toFixed(1),
          tracking: Math.floor(Math.random() * 10) + 90
        },
        robotics: {
          tasks: Math.floor(Math.random() * 20) + 75,
          load: Math.floor(Math.random() * 30) + 40,
          flow: Math.floor(Math.random() * 15) + 85
        }
      };

      ws.send(JSON.stringify(liveMetrics));
    }
  }, 2000);

  ws.on('close', () => {
    console.log('[WebSocket] Client disconnected.');
    clearInterval(telemetryInterval);
  });
});

// Start Server
server.listen(PORT, () => {
  console.log(`\n==================================================`);
  console.log(`🚀 Cognitive AI Backend running on port: ${PORT}`);
  console.log(`📡 REST API Endpoint: http://localhost:${PORT}/api/cognitive/command`);
  console.log(`🔌 WebSocket Server: ws://localhost:${PORT}`);
  console.log(`==================================================\n`);
});
