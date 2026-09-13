const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const os = require('os');
const si = require('systeminformation');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

// Helper function to execute OS command line scripts
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

// OS Detection for Cross-Platform Execution
const platform = os.platform(); // 'win32', 'darwin' (macOS), or 'linux'

// API Endpoint to process and execute voice commands
app.post('/api/voice-command', async (req, res) => {
    const { command } = req.body;
    if (!command) {
        return res.json({ action: "No command detected.", speak: "I did not receive any text command." });
    }

    const lower = command.toLowerCase().trim();
    console.log(`[VOICE INPUT RECEIVED]: "${command}"`);

    // 1. ACTION: Open Google / Web Search
    if (lower.startsWith("search for") || lower.startsWith("google")) {
        const query = lower.replace("search for", "").replace("google", "").trim();
        const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
        let openCmd = `start "" "${searchUrl}"`;
        if (platform === 'darwin') openCmd = `open "${searchUrl}"`;
        if (platform === 'linux') openCmd = `xdg-open "${searchUrl}"`;

        await runOSCommand(openCmd);
        return res.json({
            action: `Performed web search for: "${query}"`,
            speak: `Searching Google for ${query}`
        });
    }

    // 2. ACTION: Open Youtube
    if (lower.includes("open youtube") || lower.includes("youtube")) {
        let openCmd = `start https://www.youtube.com`;
        if (platform === 'darwin') openCmd = `open https://www.youtube.com`;
        if (platform === 'linux') openCmd = `xdg-open https://www.youtube.com`;

        await runOSCommand(openCmd);
        return res.json({
            action: "Launched YouTube in browser.",
            speak: "Opening YouTube."
        });
    }

    // 3. ACTION: Launch Notepad / Text Editor
    if (lower.includes("open notepad") || lower.includes("launch notepad") || lower.includes("text editor")) {
        let openCmd = `notepad.exe`;
        if (platform === 'darwin') openCmd = `open -a TextEdit`;
        if (platform === 'linux') openCmd = `gedit`;

        await runOSCommand(openCmd);
        return res.json({
            action: "Launched local Notepad application.",
            speak: "Launching Notepad."
        });
    }

    // 4. ACTION: Launch Calculator
    if (lower.includes("open calculator") || lower.includes("launch calculator") || lower.includes("calc")) {
        let openCmd = `calc.exe`;
        if (platform === 'darwin') openCmd = `open -a Calculator`;
        if (platform === 'linux') openCmd = `gnome-calculator`;

        await runOSCommand(openCmd);
        return res.json({
            action: "Launched local Calculator application.",
            speak: "Opening Calculator."
        });
    }

    // 5. ACTION: Launch Command Prompt / Terminal
    if (lower.includes("open terminal") || lower.includes("open command prompt") || lower.includes("open cmd")) {
        let openCmd = `start cmd.exe`;
        if (platform === 'darwin') openCmd = `open -a Terminal`;
        if (platform === 'linux') openCmd = `x-terminal-emulator`;

        await runOSCommand(openCmd);
        return res.json({
            action: "Opened local Command Prompt / Terminal.",
            speak: "Opening terminal window."
        });
    }

    // 6. ACTION: Real System Hardware Telemetry
    if (lower.includes("system status") || lower.includes("system health") || lower.includes("cpu status")) {
        const cpuData = await si.currentLoad();
        const memData = await si.mem();
        
        const cpuLoad = Math.round(cpuData.currentLoad);
        const freeRam = (memData.free / 1024 / 1024 / 1024).toFixed(2);
        const totalRam = (memData.total / 1024 / 1024 / 1024).toFixed(2);

        const statusMessage = `CPU Usage is at ${cpuLoad} percent. Free RAM is ${freeRam} Gigabytes out of ${totalRam} Gigabytes.`;
        return res.json({
            action: `Hardware Status: CPU Load ${cpuLoad}% | RAM Free ${freeRam} GB / ${totalRam} GB`,
            speak: statusMessage
        });
    }

    // 7. ACTION: Get Current Date and Time
    if (lower.includes("time") || lower.includes("date") || lower.includes("clock")) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const dateStr = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });

        return res.json({
            action: `Current Date & Time: ${dateStr}, ${timeStr}`,
            speak: `It is ${timeStr} on ${dateStr}`
        });
    }

    // Fallback if command is not mapped
    return res.json({
        action: `Command unrecognized: "${command}".`,
        speak: `I heard ${command}, but I do not have an automated script mapped to that command yet.`
    });
});

// Serve UI via HTML endpoint
app.get('/', (req, res) => {
    res.send(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice AI Operations Control Center</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #080d1a;
            --panel-bg: #111827;
            --accent-color: #00f0ff;
            --accent-danger: #ff0055;
            --text-color: #f3f4f6;
            --text-dim: #9ca3af;
            --border-color: #1f2937;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Poppins', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            width: 100%;
            max-width: 800px;
            background-color: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
        }

        h1 {
            font-size: 1.8rem;
            color: var(--accent-color);
            text-align: center;
            margin-bottom: 10px;
            letter-spacing: 1px;
        }

        p.subtitle {
            text-align: center;
            color: var(--text-dim);
            font-size: 0.9rem;
            margin-bottom: 30px;
        }

        .btn-wrapper {
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }

        .mic-btn {
            background: linear-gradient(135deg, #00f0ff, #7000ff);
            color: #fff;
            border: none;
            padding: 16px 36px;
            border-radius: 50px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.4);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .mic-btn.listening {
            background: linear-gradient(135deg, #ff0055, #ff6600);
            box-shadow: 0 0 20px rgba(255, 0, 85, 0.6);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        .console-box {
            background-color: #040711;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            font-family: 'JetBrains Mono', monospace;
            margin-bottom: 20px;
        }

        .console-label {
            font-size: 0.75rem;
            color: var(--text-dim);
            text-transform: uppercase;
            margin-bottom: 8px;
            letter-spacing: 1px;
        }

        .console-text {
            font-size: 1rem;
            color: #fff;
            min-height: 40px;
            word-break: break-word;
        }

        .action-box {
            border-color: rgba(0, 240, 255, 0.3);
        }

        .action-text {
            color: var(--accent-color);
        }

        .commands-list {
            margin-top: 25px;
            background: rgba(255, 255, 255, 0.02);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }

        .commands-list h3 {
            font-size: 0.85rem;
            color: var(--text-dim);
            margin-bottom: 10px;
            text-transform: uppercase;
        }

        .commands-list ul {
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }

        .commands-list li {
            font-size: 0.8rem;
            background: #090e1a;
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            color: var(--text-color);
        }

        .commands-list code {
            color: var(--accent-color);
        }
    </style>
</head>
<body>

<div class="container">
    <h1>System Operations Voice Control</h1>
    <p class="subtitle">Direct Voice-to-System Execution Interface</p>

    <div class="btn-wrapper">
        <button id="micBtn" class="mic-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
            <span id="btnText">Start Voice Input</span>
        </button>
    </div>

    <div class="console-box">
        <div class="console-label">Voice Recognition Transcript</div>
        <div id="transcript" class="console-text">Awaiting microphone activation...</div>
    </div>

    <div class="console-box action-box">
        <div class="console-label">System Execution Result</div>
        <div id="actionResult" class="console-text action-text">System Ready.</div>
    </div>

    <div class="commands-list">
        <h3>Supported Commands to Speak:</h3>
        <ul>
            <li><code>"Open Notepad"</code></li>
            <li><code>"Open Calculator"</code></li>
            <li><code>"Open Terminal"</code></li>
            <li><code>"Open YouTube"</code></li>
            <li><code>"Search for [anything]"</code></li>
            <li><code>"System Status"</code></li>
            <li><code>"What is the time"</code></li>
        </ul>
    </div>
</div>

<script>
    const micBtn = document.getElementById('micBtn');
    const btnText = document.getElementById('btnText');
    const transcript = document.getElementById('transcript');
    const actionResult = document.getElementById('actionResult');

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Web Speech API is not supported in this browser. Please open this page in Google Chrome.");
    } else {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        let isListening = false;

        micBtn.addEventListener('click', () => {
            if (!isListening) {
                try {
                    recognition.start();
                    isListening = true;
                    micBtn.classList.add('listening');
                    btnText.innerText = "Listening...";
                    transcript.innerText = "Listening for your command...";
                } catch (e) {
                    console.error(e);
                }
            } else {
                recognition.stop();
                resetBtn();
            }
        });

        recognition.onresult = async (event) => {
            const commandText = event.results[0][0].transcript;
            transcript.innerText = commandText;
            actionResult.innerText = "Executing command on backend...";

            // Send voice input directly to Node.js backend
            await sendCommandToBackend(commandText);
        };

        recognition.onerror = (event) => {
            transcript.innerText = "Voice input error: " + event.error;
            resetBtn();
        };

        recognition.onend = () => {
            resetBtn();
        };

        function resetBtn() {
            isListening = false;
            micBtn.classList.remove('listening');
            btnText.innerText = "Start Voice Input";
        }
    }

    async function sendCommandToBackend(text) {
        try {
            const res = await fetch('/api/voice-command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: text })
            });

            const data = await res.json();
            actionResult.innerText = data.action;

            // Audio Response Output
            if ('speechSynthesis' in window && data.speak) {
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(data.speak);
                window.speechSynthesis.speak(utterance);
            }
        } catch (err) {
            actionResult.innerText = "Failed to communicate with local execution server.";
        }
    }
</script>

</body>
</html>
    `);
});

app.listen(PORT, () => {
    console.log(`\n==================================================`);
    console.log(` SYSTEM VOICE CONTROL HUB RUNNING SUCCESSFULLY`);
    console.log(` Access URL: http://localhost:${PORT}`);
    console.log(`==================================================\n`);
});