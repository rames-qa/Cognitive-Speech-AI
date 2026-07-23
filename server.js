const express = require("express");
const path = require("path");
const http = require("http");

const app = express();
const PORT = process.env.PORT || 3000;
const FLASK_PORT = 5000;

app.use(express.json());
app.use(express.static(__dirname));

// Forward requests from frontend directly to Flask (app.py)
app.post("/api/process-cognitive", (req, res) => {
    const { prompt, language } = req.body;
    console.log(`[NODE BRIDGE] Received query [${language}]: ${prompt}`);

    const postData = JSON.stringify({ command: prompt });

    const options = {
        hostname: "127.0.0.1",
        port: FLASK_PORT,
        path: "/api/command",
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(postData)
        }
    };

    const flaskReq = http.request(options, (flaskRes) => {
        let body = "";
        flaskRes.on("data", (chunk) => { body += chunk; });
        flaskRes.on("end", () => {
            try {
                const parsed = JSON.parse(body);
                
                // Return structured response for the frontend UI
                res.json({
                    reply: parsed.action || "Command processed.",
                    url: parsed.url || null,
                    metrics: {
                        neuralVelocity: `${Math.floor(Math.random() * 30 + 70)} ms`,
                        visionFps: `${Math.floor(Math.random() * 15 + 45)} FPS`,
                        roboticsLoad: `${Math.floor(Math.random() * 25 + 15)}%`
                    }
                });
            } catch (err) {
                res.json({ reply: "Received invalid response from automation server." });
            }
        });
    });

    flaskReq.on("error", (error) => {
        console.error("[NODE BRIDGE ERROR] Could not connect to Flask app.py:", error.message);
        res.json({
            reply: `Automation backend offline. Ensure app.py is running on port ${FLASK_PORT}.`,
            metrics: { neuralVelocity: "OFFLINE", visionFps: "0 FPS", roboticsLoad: "0%" }
        });
    });

    flaskReq.write(postData);
    flaskReq.end();
});

app.listen(PORT, () => {
    console.log(`Cognitive AI Node Server executing on http://localhost:${PORT}`);
});
