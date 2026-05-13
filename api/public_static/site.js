const state = {
  messages: [],
  models: [],
  abortController: null,
  activeAssistantId: null,
};

const STORAGE_KEYS = {
  apiKey: "fcc_web_api_key",
  rememberToken: "fcc_web_remember_token",
  model: "fcc_web_model",
  maxTokens: "fcc_web_max_tokens",
  systemPrompt: "fcc_web_system_prompt",
  transcript: "fcc_web_transcript",
};

const byId = (id) => document.getElementById(id);

function setStatus(text, tone = "neutral") {
  const pill = byId("statusPill");
  pill.textContent = text;
  pill.dataset.tone = tone;
}

function setConnectionState(text, detail) {
  byId("connectionState").textContent = text;
  byId("connectionDetail").textContent = detail;
}

function loadSettings() {
  byId("rememberToken").checked = localStorage.getItem(STORAGE_KEYS.rememberToken) !== "false";
  byId("apiKey").value = localStorage.getItem(STORAGE_KEYS.apiKey) || "";
  byId("systemPrompt").value = localStorage.getItem(STORAGE_KEYS.systemPrompt) || "";
  byId("maxTokens").value = localStorage.getItem(STORAGE_KEYS.maxTokens) || "4096";
}

function saveSettings() {
  localStorage.setItem(STORAGE_KEYS.rememberToken, String(byId("rememberToken").checked));
  localStorage.setItem(STORAGE_KEYS.systemPrompt, byId("systemPrompt").value);
  localStorage.setItem(STORAGE_KEYS.maxTokens, byId("maxTokens").value || "4096");

  if (byId("rememberToken").checked) {
    localStorage.setItem(STORAGE_KEYS.apiKey, byId("apiKey").value.trim());
  } else {
    localStorage.removeItem(STORAGE_KEYS.apiKey);
  }

  localStorage.setItem(STORAGE_KEYS.model, byId("modelSelect").value || "");
}

function loadTranscript() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.transcript);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter(
          (message) => message && (message.role === "user" || message.role === "assistant"),
        )
      : [];
  } catch {
    return [];
  }
}

function saveTranscript() {
  const transcript = state.messages
    .filter((message) => !message.pending)
    .map((message) => ({ role: message.role, content: message.content }));
  localStorage.setItem(STORAGE_KEYS.transcript, JSON.stringify(transcript));
  byId("messageCount").textContent = `${transcript.length} messages`;
}

function renderTranscript() {
  const messagesEl = byId("messages");
  messagesEl.innerHTML = "";

  state.messages.forEach((message) => {
    const element = createMessageElement(message);
    message.element = element;
    messagesEl.appendChild(element);
  });

  scrollMessagesToBottom();
  saveTranscript();
}

function createMessageElement(message) {
  const wrapper = document.createElement("article");
  wrapper.className = `message ${message.role}${message.pending ? " pending" : ""}`;

  const meta = document.createElement("div");
  meta.className = "message-meta";
  const roleLabel = message.role === "user" ? "You" : "Claude Code";
  meta.innerHTML = `<span>${roleLabel}</span><span>${message.pending ? "Streaming" : ""}</span>`;

  const content = document.createElement("div");
  content.className = "message-content";
  content.textContent = message.content || "";

  wrapper.append(meta, content);
  return wrapper;
}

function scrollMessagesToBottom() {
  const messagesEl = byId("messages");
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendMessage(role, content, options = {}) {
  const message = {
    role,
    content,
    pending: Boolean(options.pending),
    element: null,
  };
  state.messages.push(message);
  const element = createMessageElement(message);
  message.element = element;
  byId("messages").appendChild(element);
  scrollMessagesToBottom();
  saveTranscript();
  return message;
}

function updateMessage(message, content, pending = message.pending) {
  message.content = content;
  message.pending = pending;
  message.element.className = `message ${message.role}${pending ? " pending" : ""}`;
  const contentEl = message.element.querySelector(".message-content");
  contentEl.textContent = content;
  const meta = message.element.querySelector(".message-meta span:last-child");
  meta.textContent = pending ? "Streaming" : "";
  scrollMessagesToBottom();
}

function clearConversation() {
  if (state.abortController) {
    state.abortController.abort();
    state.abortController = null;
  }

  state.messages = [];
  byId("messages").innerHTML = "";
  localStorage.removeItem(STORAGE_KEYS.transcript);
  byId("messageCount").textContent = "0 messages";
  byId("stopButton").disabled = true;
  setStatus("Idle");
  setConnectionState("Disconnected", "Enter a token to start a session.");
}

function exportTranscript() {
  const transcript = state.messages
    .filter((message) => !message.pending)
    .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
    .join("\n\n");

  const blob = new Blob([transcript || ""], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "free-claude-code-transcript.txt";
  link.click();
  URL.revokeObjectURL(link.href);
}

function getHeaders() {
  const token = byId("apiKey").value.trim();
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["X-API-Key"] = token;
  }
  return headers;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!response.ok) {
    const detail =
      body && typeof body === "object"
        ? body.detail || body.error?.message || body.message || response.statusText
        : text || response.statusText;
    throw new Error(detail);
  }
  return body;
}

function setSendState(isSending) {
  byId("sendButton").disabled = isSending;
  byId("stopButton").disabled = !isSending;
  byId("loadModels").disabled = isSending;
  byId("clearChat").disabled = isSending;
  byId("exportChat").disabled = isSending;
  byId("modelSelect").disabled = isSending || state.models.length === 0;
  byId("apiKey").disabled = isSending;
}

function parseSseBlock(block) {
  const event = { name: "message", data: "" };
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      event.name = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      const value = line.slice(5).replace(/^\s/, "");
      event.data = event.data ? `${event.data}\n${value}` : value;
    }
  }
  return event;
}

async function streamSse(response, handleEvent) {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let splitIndex = buffer.indexOf("\n\n");
    while (splitIndex !== -1) {
      const rawEvent = buffer.slice(0, splitIndex).trim();
      buffer = buffer.slice(splitIndex + 2);
      if (rawEvent) {
        handleEvent(parseSseBlock(rawEvent));
      }
      splitIndex = buffer.indexOf("\n\n");
    }

    if (done) {
      const tail = buffer.trim();
      if (tail) {
        handleEvent(parseSseBlock(tail));
      }
      break;
    }
  }
}

function buildConversation() {
  return state.messages
    .filter((message) => !message.pending)
    .map((message) => ({ role: message.role, content: message.content }));
}

async function refreshModels() {
  const token = byId("apiKey").value.trim();
  if (!token) {
    setConnectionState("Disconnected", "Add an API token before loading models.");
    setStatus("Token required", "warn");
    return;
  }

  setStatus("Loading models", "warn");
  setConnectionState("Connecting", "Fetching model list from the proxy.");

  try {
    const data = await fetchJson("/v1/models", { headers: getHeaders() });
    state.models = Array.isArray(data.data) ? data.data : [];

    const modelSelect = byId("modelSelect");
    modelSelect.innerHTML = "";
    state.models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.display_name ? `${model.display_name} (${model.id})` : model.id;
      modelSelect.appendChild(option);
    });

    const savedModel = localStorage.getItem(STORAGE_KEYS.model);
    if (savedModel && state.models.some((model) => model.id === savedModel)) {
      modelSelect.value = savedModel;
    } else if (state.models.length > 0) {
      modelSelect.value = state.models[0].id;
    }

    setConnectionState("Connected", `${state.models.length} models available.`);
    setStatus("Ready", "ok");
  } catch (error) {
    state.models = [];
    byId("modelSelect").innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Load models to continue";
    byId("modelSelect").appendChild(option);
    setConnectionState("Disconnected", error.message || "Could not load models.");
    setStatus("Offline", "error");
  }
}

async function checkServer() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error(response.statusText);
    byId("serverOrigin").textContent = location.origin;
  } catch {
    byId("serverOrigin").textContent = location.origin;
  }
}

async function sendMessage(promptText) {
  if (state.abortController) {
    return;
  }

  const model = byId("modelSelect").value;
  if (!model) {
    throw new Error("Load a model before sending a message.");
  }

  const token = byId("apiKey").value.trim();
  if (!token) {
    throw new Error("Add your API token first.");
  }

  const maxTokens = Number.parseInt(byId("maxTokens").value, 10);
  const conversation = buildConversation();
  appendMessage("user", promptText);
  const assistantMessage = appendMessage("assistant", "", { pending: true });

  state.abortController = new AbortController();
  setSendState(true);
  setStatus("Streaming", "warn");

  try {
    const response = await fetch("/v1/messages", {
      method: "POST",
      headers: getHeaders(),
      signal: state.abortController.signal,
      body: JSON.stringify({
        model,
        max_tokens: Number.isFinite(maxTokens) ? maxTokens : 4096,
        stream: true,
        system: byId("systemPrompt").value.trim() || undefined,
        messages: [...conversation, { role: "user", content: promptText }],
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || response.statusText);
    }

    let assistantText = "";
    await streamSse(response, (event) => {
      if (event.name === "content_block_delta") {
        try {
          const payload = JSON.parse(event.data);
          if (payload.delta?.type === "text_delta" && typeof payload.delta.text === "string") {
            assistantText += payload.delta.text;
            updateMessage(assistantMessage, assistantText, true);
          }
        } catch {
          // Ignore malformed blocks and keep streaming the response.
        }
      } else if (event.name === "message_stop") {
        updateMessage(assistantMessage, assistantText, false);
        setStatus("Ready", "ok");
      } else if (event.name === "error") {
        try {
          const payload = JSON.parse(event.data);
          throw new Error(payload.error?.message || payload.message || "Streaming error");
        } catch {
          throw new Error("Streaming error");
        }
      }
    });

    updateMessage(assistantMessage, assistantText, false);
    assistantMessage.pending = false;
    saveTranscript();
    setConnectionState("Connected", `Last response from ${model}.`);
  } catch (error) {
    updateMessage(assistantMessage, assistantMessage.content || "Request failed.", false);
    assistantMessage.element.classList.add("error");
    assistantMessage.content = `${assistantMessage.content || ""}${assistantMessage.content ? "\n\n" : ""}${error.message || "Request failed."}`;
    assistantMessage.element.querySelector(".message-content").textContent = assistantMessage.content;
    setStatus("Error", "error");
    setConnectionState("Disconnected", error.message || "Request failed.");
  } finally {
    state.abortController = null;
    setSendState(false);
    byId("promptInput").focus();
    saveTranscript();
  }
}

function restoreTranscript() {
  state.messages = loadTranscript();
  renderTranscript();
}

function wireEvents() {
  byId("rememberToken").addEventListener("change", saveSettings);
  byId("apiKey").addEventListener("change", () => {
    saveSettings();
    refreshModels();
  });
  byId("apiKey").addEventListener("keyup", (event) => {
    if (event.key === "Enter") {
      refreshModels();
    }
  });
  byId("systemPrompt").addEventListener("input", saveSettings);
  byId("maxTokens").addEventListener("change", saveSettings);
  byId("modelSelect").addEventListener("change", saveSettings);

  byId("loadModels").addEventListener("click", async () => {
    saveSettings();
    await refreshModels();
  });

  byId("copyLink").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(`${location.origin}/chat`);
      setStatus("Link copied", "ok");
    } catch {
      setStatus("Copy failed", "warn");
    }
  });

  byId("clearChat").addEventListener("click", clearConversation);
  byId("exportChat").addEventListener("click", exportTranscript);

  byId("stopButton").addEventListener("click", () => {
    if (state.abortController) {
      state.abortController.abort();
      setStatus("Stopped", "warn");
      byId("stopButton").disabled = true;
    }
  });

  byId("composer").addEventListener("submit", async (event) => {
    event.preventDefault();
    const promptInput = byId("promptInput");
    const promptText = promptInput.value.trim();
    if (!promptText || state.abortController) {
      return;
    }

    saveSettings();
    promptInput.value = "";
    try {
      await sendMessage(promptText);
    } catch (error) {
      setStatus("Error", "error");
      setConnectionState("Disconnected", error.message || "Request failed.");
    }
  });

  byId("promptInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      byId("composer").requestSubmit();
    }
  });
}

async function init() {
  byId("serverOrigin").textContent = location.origin;
  loadSettings();
  restoreTranscript();
  wireEvents();
  setSendState(false);
  setStatus("Idle");
  await checkServer();
  if (byId("apiKey").value.trim()) {
    await refreshModels();
  } else {
    byId("modelSelect").innerHTML = '<option value="">Add an API token to load models</option>';
    setConnectionState("Disconnected", "Enter a token to load your model list.");
    setStatus("Token required", "warn");
  }
}

init().catch((error) => {
  setStatus("Startup failed", "error");
  setConnectionState("Disconnected", error.message || "Unable to load the page.");
});