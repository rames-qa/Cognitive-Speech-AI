const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const os = require('os');
const si = require('systeminformation');
const http = require('http');

const app = express();
const PORT = process.env.PORT || 3000;
const FLASK_PORT = 5000;

app.use(cors());
app.use(express.json());
app.use(express.static(__dirname));

const platform = os.platform();

function runOSCommand(cmd) {
    return new Promise((resolve) => {
        exec(cmd, (error, stdout, stderr) => {
            if (error) {
                resolve({ success: false, output: stderr || error.message });
            } else {
                resolve({ success: true, output: stdout.trim() });
            }
        });
    });
}

// Route handling for both local OS actions and Python automation bridge
app.post('/api/process-cognitive', async (req, res) => {
    const { prompt } = req.body;
    if (!prompt) {
        return res.json({ reply: "No command received." });
    }

    const lower = prompt.toLowerCase().trim();
    console.log(`[COGNITIVE PROCESSING]: "${prompt}"`);

    // --- 1. LOCAL OS AUTOMATIONS ---
    if (lower.includes("open notepad") || lower.includes("launch notepad")) {
        let cmd = platform === 'win32' ? 'notepad.exe' : (platform === 'darwin' ? 'open -a TextEdit' : 'gedit');
        await runOSCommand(cmd);
        return res.json({ reply: "Launching Notepad application." });
    }

    if (lower.includes("open calculator") || lower.includes("calc")) {
        let cmd = platform === 'win32' ? 'calc.exe' : (platform === 'darwin' ? 'open -a Calculator' : 'gnome-calculator');
        await runOSCommand(cmd);
        return res.json({ reply: "Opening local Calculator." });
    }

    if (lower.includes("open terminal") || lower.includes("open cmd")) {
        let cmd = platform === 'win32' ? 'start cmd.exe' : (platform === 'darwin' ? 'open -a Terminal' : 'x-terminal-emulator');
        await runOSCommand(cmd);
        return res.json({ reply: "Opening command terminal." });
    }

    if (lower.includes("system status") || lower.includes("cpu status")) {
        const cpuData = await si.currentLoad();
        const memData = await si.mem();
        const cpuLoad = Math.round(cpuData.currentLoad);
        const freeRam = (memData.free / 1024 / 1024 / 1024).toFixed(2);
        const totalRam = (memData.total / 1024 / 1024 / 1024).toFixed(2);

        return res.json({
            reply: `System CPU load is at ${cpuLoad}%. Free RAM is ${freeRam} GB out of ${totalRam} GB.`,
            metrics: {
                neuralVelocity: `${cpuLoad}% Load`,
                visionFps: `${freeRam} GB Free`,
                roboticsLoad: `${totalRam} GB Total`
            }
        });
    }

    // --- 2. FALLBACK TO PYTHON FLASK AUTOMATION ENGINE (app.py) ---
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
                res.json({
                    reply: parsed.action || "Command processed.",
                    url: parsed.url || null
                });
            } catch (err) {
                res.json({ reply: "Received invalid response from Flask backend." });
            }
        });
    });

    flaskReq.on("error", () => {
        res.json({ reply: `Processed request locally or Flask backend offline.` });
    });

    flaskReq.write(postData);
    flaskReq.end();
});

app.listen(PORT, () => {
    console.log(`Unified Voice & OS Hub active on http://localhost:${PORT}`);
});
