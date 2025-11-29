document.addEventListener("DOMContentLoaded", () => {
    const translateBtn = document.getElementById("translateButton");
    const clearBtn = document.getElementById("clearButton");
    const inputText = document.getElementById("inputText");
    const outputText = document.getElementById("outputText");
    const sourceLanguage = document.getElementById("sourceLanguage");
    const targetLanguage = document.getElementById("targetLanguage");
    const loadingIndicator = document.getElementById("loadingIndicator");
    const swapLanguages = document.getElementById("swapLanguages");
    const inputCount = document.getElementById("inputCount");
    const outputCount = document.getElementById("outputCount");

    inputCount.textContent = `${inputText.value.length}/5000`;
    outputCount.textContent = `${outputText.value.length}/5000`;

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
});
