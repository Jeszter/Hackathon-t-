document.addEventListener("DOMContentLoaded", () => {
    const translateBtn = document.getElementById("translateButton");
    const clearBtn = document.getElementById("clearButton");
    const inputText = document.getElementById("inputText");
    const outputText = document.getElementById("outputText");
    const sourceLanguage = document.getElementById("sourceLanguage");
    const targetLanguage = document.getElementById("targetLanguage");
    const voiceTargetLanguage = document.getElementById("voiceTargetLanguage");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const swapLanguages = document.getElementById("swapLanguages");
    const inputCount = document.getElementById("inputCount");
    const outputCount = document.getElementById("outputCount");

    const methodButtons = document.querySelectorAll(".method-btn");
    const textInputArea = document.querySelector(".text-input-area");
    const voiceInputArea = document.querySelector(".voice-input-area");
    const imageInputArea = document.querySelector(".image-upload-area");

    const voiceButton = document.getElementById("voiceButton");
    const voiceStatus = document.getElementById("voiceStatus");
    const voiceResult = document.getElementById("voiceResult");

    inputCount.textContent = `${inputText.value.length}/5000`;
    outputCount.textContent = `${outputText.value.length}/5000`;

    if (voiceTargetLanguage && targetLanguage) {
        voiceTargetLanguage.value = targetLanguage.value;
    }

    function showMethod(method) {
        if (textInputArea) textInputArea.style.display = method === "text" ? "block" : "none";
        if (voiceInputArea) voiceInputArea.style.display = method === "voice" ? "block" : "none";
        if (imageInputArea) imageInputArea.style.display = method === "image" ? "block" : "none";
    }

    showMethod("text");

    methodButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            methodButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const method = btn.getAttribute("data-method");
            showMethod(method);
        });
    });

    targetLanguage.addEventListener("change", () => {
        if (voiceTargetLanguage) voiceTargetLanguage.value = targetLanguage.value;
    });

    if (voiceTargetLanguage) {
        voiceTargetLanguage.addEventListener("change", () => {
            targetLanguage.value = voiceTargetLanguage.value;
        });
    }

    inputText.addEventListener("input", () => {
        inputCount.textContent = `${inputText.value.length}/5000`;
    });

    outputText.addEventListener("input", () => {
        outputCount.textContent = `${outputText.value.length}/5000`;
    });

    swapLanguages.addEventListener("click", () => {
        const src = sourceLanguage.value;
        const tgt = targetLanguage.value;
        sourceLanguage.value = tgt;
        targetLanguage.value = src;
        if (voiceTargetLanguage) voiceTargetLanguage.value = targetLanguage.value;
        const temp = inputText.value;
        inputText.value = outputText.value;
        outputText.value = temp;
        inputCount.textContent = `${inputText.value.length}/5000`;
        outputCount.textContent = `${outputText.value.length}/5000`;
    });

    clearBtn.addEventListener("click", () => {
        inputText.value = "";
        outputText.value = "";
        inputCount.textContent = "0/5000";
        outputCount.textContent = "0/5000";
        if (voiceResult) voiceResult.textContent = "";
        if (voiceStatus) voiceStatus.textContent = "Click to start speaking";
    });

    translateBtn.addEventListener("click", async () => {
        const text = inputText.value.trim();
        const srcLang = sourceLanguage.value;
        const tgtLang = targetLanguage.value;

        if (!text) {
            alert("Please enter text to translate.");
            return;
        }

        loadingIndicator.style.display = "flex";

        try {
            const response = await fetch("/translation", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: text,
                    source_language: srcLang,
                    target_language: tgtLang
                })
            });

            const data = await response.json();
            loadingIndicator.style.display = "none";

            if (data.status === "success") {
                outputText.value = data.translated_text;
                outputCount.textContent = `${outputText.value.length}/5000`;
            } else {
                outputText.value = "Translation failed.";
                outputCount.textContent = `${outputText.value.length}/5000`;
            }
        } catch (error) {
            loadingIndicator.style.display = "none";
            outputText.value = "Server error. Try again.";
            outputCount.textContent = `${outputText.value.length}/5000`;
        }
    });

    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let recorderMimeType = "audio/webm";

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            let options = {};
            const preferred = "audio/webm;codecs=opus";
            if (window.MediaRecorder && MediaRecorder.isTypeSupported(preferred)) {
                options.mimeType = preferred;
                recorderMimeType = preferred;
            } else if (window.MediaRecorder && MediaRecorder.isTypeSupported("audio/webm")) {
                options.mimeType = "audio/webm";
                recorderMimeType = "audio/webm";
            } else {
                recorderMimeType = "";
            }

            mediaRecorder = recorderMimeType ? new MediaRecorder(stream, options) : new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = async () => {
                if (!audioChunks.length) {
                    if (voiceStatus) voiceStatus.textContent = "No audio recorded. Try again.";
                    return;
                }

                const blobType = recorderMimeType || "audio/webm";
                const audioBlob = new Blob(audioChunks, { type: blobType });
                const formData = new FormData();
                formData.append("audio", audioBlob, "speech.webm");
                const voiceLang = voiceTargetLanguage ? voiceTargetLanguage.value : targetLanguage.value || "en";
                formData.append("target_language", voiceLang);

                if (loadingIndicator) loadingIndicator.style.display = "flex";
                if (voiceStatus) voiceStatus.textContent = "Processing audio...";
                if (voiceResult) voiceResult.textContent = "";

                try {
                    const resp = await fetch("/translation/voice", {
                        method: "POST",
                        body: formData
                    });

                    const data = await resp.json();
                    if (loadingIndicator) loadingIndicator.style.display = "none";

                    if (data.status === "success") {
                        const recognized = data.transcribed_text || data.recognized_text || "";
                        const translated = data.translated_text || "";

                        inputText.value = recognized;
                        outputText.value = translated;
                        inputCount.textContent = `${inputText.value.length}/5000`;
                        outputCount.textContent = `${outputText.value.length}/5000`;

                        if (voiceResult) {
                            voiceResult.innerHTML =
                                `<div><strong>Recognized:</strong> ${recognized || "(empty)"}</div>` +
                                `<div><strong>Translated:</strong> ${translated || "(empty)"}</div>`;
                        }

                        if (voiceStatus) voiceStatus.textContent = "Click to start speaking";
                    } else {
                        if (voiceStatus) voiceStatus.textContent = "Error during processing. Try again.";
                        if (voiceResult) voiceResult.textContent = data.message || "Voice translation failed.";
                    }
                } catch (e) {
                    if (loadingIndicator) loadingIndicator.style.display = "none";
                    if (voiceStatus) voiceStatus.textContent = "Server error. Try again.";
                    if (voiceResult) voiceResult.textContent = "Server error. Try again.";
                }
            };

            mediaRecorder.start();
            isRecording = true;
            if (voiceButton) voiceButton.classList.add("recording");
            if (voiceStatus) voiceStatus.textContent = "Listening... click to stop";
            if (voiceResult) voiceResult.textContent = "";
        } catch (err) {
            isRecording = false;
            mediaRecorder = null;
            if (voiceStatus) {
                if (!navigator.mediaDevices || !window.MediaRecorder) {
                    voiceStatus.textContent = "Browser does not support voice recording. Try Chrome or Edge.";
                } else {
                    voiceStatus.textContent = "Microphone access denied.";
                }
            }
        }
    }

    function stopRecording() {
        if (mediaRecorder && isRecording) {
            mediaRecorder.stop();
            isRecording = false;
            if (voiceButton) voiceButton.classList.remove("recording");
        }
    }

    if (voiceButton) {
        voiceButton.addEventListener("click", () => {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });
    }
});
