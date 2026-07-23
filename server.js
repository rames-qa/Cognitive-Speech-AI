const express = require("express");
const path = require("path");
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// Endpoint matching the frontend fetch call
app.post("/api/process-cognitive", async (req, res) => {
    const { prompt, language } = req.body;

    console.log(`Received query [${language}]: ${prompt}`);

    // Example AI integration logic (Place Gemini / OpenAI SDK calls here)
    const simulatedAIResponse = `System verified command: "${prompt}". Processing telemetry matrices in real-time.`;

    res.json({
        reply: simulatedAIResponse,
        metrics: {
            neuralVelocity: `${Math.floor(Math.random() * 40 + 60)} ms`,
            visionFps: `${Math.floor(Math.random() * 15 + 45)} FPS`,
            roboticsLoad: `${Math.floor(Math.random() * 30 + 20)}%`
        }
    });
});

app.listen(PORT, () => {
    console.log(`Cognitive AI Server executing on http://localhost:${PORT}`);
});
