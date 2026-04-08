function stripCodeFence(rawText) {
    return String(rawText || "")
        .replace(/^```json\s*/i, "")
        .replace(/^```\s*/i, "")
        .replace(/\s*```$/i, "")
        .trim();
}

function appendSectionText(target, line) {
    if (!line) return target;
    return target ? `${target}\n${line}` : line;
}

function parsePlainTextQuestion(rawText) {
    const lines = stripCodeFence(rawText).split(/\r?\n/);
    const parsed = {
        question: "",
        options: {},
        answer: "",
        analysis: "",
    };
    let currentSection = "question";

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) continue;

        const questionMatch = line.match(/^题目[：:]\s*(.*)$/);
        const optionMatch = line.match(/^([A-H])[\.．、:：]\s*(.+)$/i);
        const answerMatch = line.match(/^答案[：:]\s*(.*)$/);
        const analysisMatch = line.match(/^解析[：:]\s*(.*)$/);

        if (questionMatch) {
            currentSection = "question";
            parsed.question = appendSectionText(parsed.question, questionMatch[1]);
            continue;
        }

        if (optionMatch) {
            currentSection = "options";
            parsed.options[optionMatch[1].toUpperCase()] = optionMatch[2];
            continue;
        }

        if (answerMatch) {
            currentSection = "answer";
            parsed.answer = appendSectionText(parsed.answer, answerMatch[1]);
            continue;
        }

        if (analysisMatch) {
            currentSection = "analysis";
            parsed.analysis = appendSectionText(parsed.analysis, analysisMatch[1]);
            continue;
        }

        if (currentSection === "question") {
            parsed.question = appendSectionText(parsed.question, line);
        } else if (currentSection === "answer") {
            parsed.answer = appendSectionText(parsed.answer, line);
        } else if (currentSection === "analysis") {
            parsed.analysis = appendSectionText(parsed.analysis, line);
        }
    }

    return {
        question: parsed.question.trim(),
        options: Object.keys(parsed.options).length ? parsed.options : null,
        answer: parsed.answer.trim(),
        analysis: parsed.analysis.trim(),
    };
}

export function parseQuestionPayload(rawText) {
    const cleaned = stripCodeFence(rawText);

    try {
        const parsed = JSON.parse(cleaned);
        return {
            question: String(parsed.question || "").trim(),
            options: parsed.options || null,
            answer: String(parsed.answer || "").trim(),
            analysis: String(parsed.analysis || "").trim(),
        };
    } catch (error) {
        const parsed = parsePlainTextQuestion(cleaned);
        if (parsed.question) return parsed;
        return {
            question: cleaned,
            options: null,
            answer: "",
            analysis: "",
        };
    }
}

export function normalizeQuestionPayload(payload, fallbackRaw = "") {
    if (!payload) {
        return parseQuestionPayload(fallbackRaw);
    }

    if (typeof payload === "string") {
        return parseQuestionPayload(payload);
    }

    const normalized = {
        question: String(payload.question || "").trim(),
        options: payload.options || null,
        answer: String(payload.answer || "").trim(),
        analysis: String(payload.analysis || "").trim(),
    };

    if (normalized.options || normalized.answer || normalized.analysis) {
        return normalized;
    }

    return parseQuestionPayload(normalized.question || fallbackRaw);
}

export function buildStreamPreview(rawText) {
    const cleaned = stripCodeFence(rawText);
    if (!cleaned) return "";

    const lines = cleaned.split(/\r?\n/);
    const previewLines = [];
    for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        const trimmed = line.trim();
        if (/^答案[：:]/.test(trimmed) || /^解析[：:]/.test(trimmed)) {
            break;
        }
        previewLines.push(line);
    }
    return previewLines.join("\n").trim();
}

export function buildQuestionText(questionData, questionOptions) {
    if (!questionData) return "";
    let content = questionData.question || "";
    if (questionOptions.length) {
        content += "\n\n选项：\n";
        for (const [key, value] of questionOptions) {
            content += `${key}. ${value}\n`;
        }
    }
    return content.trim();
}
