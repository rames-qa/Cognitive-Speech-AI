<!-- ... Rest of your dashboard sections and footer above ... -->

    <footer> 
        &copy; 2026 Cognitive AI Advanced Web Project | Designed by Ramesh Kumar K
    </footer>

    <!-- REPLACE THE OLD SCRIPT TAG WITH THIS: -->
    <script>
        /**
         * Cognitive AI - Voice Interface & Signal Engine
         * Handles Speech Recognition, Dashboard Component Activation, and Live Canvas Telemetry
         */

        // --- 1. Global State Configuration ---
        const SystemState = {
            activeModule: null,
            workingMode: "STANDBY",
            animationFrameIds: { neural: null, analytics: null, automation: null },
            canvasContexts: {},
            waveOffsets: { neural: 0, analytics: 0, automation: 0 }
        };

        // --- 2. Initialize Web Speech API ---
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const voiceButton = document.getElementById('btnVoiceTrigger');
        const statusDot = document.getElementById('voiceStatusDot');
        const statusText = document.getElementById('voiceStatusText');
        const transcriptBox = document.getElementById('voiceTranscript');

        let recognition = null;

        if (SpeechRecognition) {
            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.lang = 'en-US';
            recognition.interimResults = false;

            recognition.onstart = () => {
                voiceButton.classList.add('listening');
                voiceButton.innerHTML = `
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="spin-icon">
                        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                    </svg> Listening...`;
                statusDot.classList.add('active');
                statusText.innerText = "Acoustic Engine Active";
                transcriptBox.innerText = "Listening for control phrase...";
            };

            recognition.onerror = (event) => {
                console.error("Speech Error:", event.error);
                resetVoiceUI("Error Detecting Audio");
            };

            recognition.onend = () => {
                resetVoiceUI("Acoustic Engine Offline");
            };

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript.toLowerCase();
                transcriptBox.innerHTML = `Received: "<span>${event.results[0][0].transcript}</span>"`;
                processVoiceCommand(transcript);
            };
        } else {
            voiceButton.style.display = "none";
            transcriptBox.innerText = "Web Speech API is not supported in this browser.";
        }

        function resetVoiceUI(msg) {
            voiceButton.classList.remove('listening');
            voiceButton.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
                    <path d="M19 10v1a7 7 0 0 1-14 0v-1"/>
                    <line x1="12" x2="12" y1="19" y2="22"/>
                </svg> Initialize Voice Listening`;
            statusDot.classList.remove('active');
            statusText.innerText = msg;
        }

        // --- 3. Command Processing & Mode Routing ---
        function processVoiceCommand(cmd) {
            document.querySelectorAll('.dashboard-box').forEach(box => box.classList.remove('voice-pulse-highlight'));
            
            let targetModule = null;
            let modeDescription = "";

            if (cmd.includes("neural") || cmd.includes("processing") || cmd.includes("brain")) {
                targetModule = "neural";
                SystemState.workingMode = "COGNITIVE MATRIX SYNAPSE";
                modeDescription = "Mode: Synaptic Overclocking. Animating logic arrays.";
                animateProgressBar("neuralBar", 94);
            } 
            else if (cmd.includes("analytics") || cmd.includes("smart") || cmd.includes("data")) {
                targetModule = "analytics";
                SystemState.workingMode = "PREDICTIVE VECTOR EVALUATION";
                modeDescription = "Mode: High-Precision Forecasting. Charting pattern matrices.";
                animateProgressBar("analyticsBar", 99);
            } 
            else if (cmd.includes("automation") || cmd.includes("engine") || cmd.includes("robot")) {
                targetModule = "automation";
                SystemState.workingMode = "AUTONOMOUS ORCHESTRATION";
                modeDescription = "Mode: Thread Scaling. Dispatched background processes.";
                animateProgressBar("automationBar", 84);
            } 
            else if (cmd.includes("sync") || cmd.includes("all") || cmd.includes("system")) {
                triggerGlobalSync();
                return;
            }
            else {
                SystemState.workingMode = "UNKNOWN PARAMETER";
                transcriptBox.innerHTML += `<br><small style="color:#ef4444;">Command unmapped. Try saying 'Neural', 'Analytics', or 'Automation'.</small>`;
                return;
            }

            if (targetModule) {
                SystemState.activeModule = targetModule;
                const box = document.getElementById(`${targetModule}Box`);
                if (box) box.classList.add('voice-pulse-highlight');
                
                statusText.innerText = SystemState.workingMode;
                transcriptBox.innerHTML += `<br><strong style="color:#10b981;">${modeDescription}</strong>`;
            }
        }

        function animateProgressBar(barId, targetValue) {
            const bar = document.getElementById(barId);
            if (bar) {
                bar.style.width = "0%";
                setTimeout(() => {
                    bar.style.width = `${targetValue}%`;
                }, 100);
            }
        }

        // --- 4. Signal Telemetry Rendering Engine (Canvas) ---
        function initCanvasTelemetry() {
            const modules = ["neural", "analytics", "automation"];
            
            modules.forEach(mod => {
                const canvas = document.getElementById(`${mod}Canvas`);
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                SystemState.canvasContexts[mod] = ctx;
                
                canvas.width = canvas.clientWidth;
                canvas.height = canvas.clientHeight;
                
                window.addEventListener('resize', () => {
                    canvas.width = canvas.clientWidth;
                    canvas.height = canvas.clientHeight;
                });

                renderSignalWave(mod);
            });
        }

        function renderSignalWave(mod) {
            const ctx = SystemState.canvasContexts[mod];
            const canvas = document.getElementById(`${mod}Canvas`);
            if (!ctx || !canvas) return;

            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            const isSelected = (SystemState.activeModule === mod);
            const amplitude = isSelected ? 22 : 6;  
            const frequency = isSelected ? 0.04 : 0.015;
            const speed = isSelected ? 0.12 : 0.03;
            
            let strokeGradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
            if (mod === "neural") {
                strokeGradient.addColorStop(0, '#00ffff');
                strokeGradient.addColorStop(1, '#8b5cf6');
            } else if (mod === "analytics") {
                strokeGradient.addColorStop(0, '#8b5cf6');
                strokeGradient.addColorStop(1, '#10b981');
            } else {
                strokeGradient.addColorStop(0, '#10b981');
                strokeGradient.addColorStop(1, '#38bdf8');
            }

            ctx.beginPath();
            ctx.lineWidth = isSelected ? 2.5 : 1.2;
            ctx.strokeStyle = strokeGradient;

            SystemState.waveOffsets[mod] += speed;
            for (let x = 0; x < canvas.width; x++) {
                const y = (canvas.height / 2) + Math.sin(x * frequency + SystemState.waveOffsets[mod]) * amplitude;
                if (x === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            ctx.stroke();

            SystemState.animationFrameIds[mod] = requestAnimationFrame(() => renderSignalWave(mod));
        }

        // --- 5. Manual Fallback & Global Handlers ---
        function triggerGlobalSync() {
            SystemState.activeModule = null;
            SystemState.workingMode = "FULL CORE ALIGNMENT";
            statusText.innerText = SystemState.workingMode;
            transcriptBox.innerHTML = "🎯 Manual Sync: Broadcasting signal updates across all engines simultaneously.";
            
            document.querySelectorAll('.dashboard-box').forEach(box => box.classList.add('voice-pulse-highlight'));
            animateProgressBar("neuralBar", 94);
            animateProgressBar("analyticsBar", 99);
            animateProgressBar("automationBar", 84);
        }

        // --- 6. Event Initializers ---
        voiceButton.addEventListener('click', () => {
            if (recognition) {
                try {
                    recognition.start();
                } catch (e) {
                    recognition.stop();
                }
            }
        });

        document.getElementById('btnManualSync').addEventListener('click', triggerGlobalSync);
        window.addEventListener('DOMContentLoaded', initCanvasTelemetry);
    </script>
</body>
</html>
