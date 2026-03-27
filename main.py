<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Ask Hope</title>
  <style>
    :root {
      --red: #c62828;
      --red-dark: #a61f1f;
      --red-soft: #fdecec;
      --text: #1f2937;
      --muted: #6b7280;
      --bg: #f5f7fb;
      --card: #ffffff;
      --border: #e5e7eb;
      --shadow: 0 18px 45px rgba(15, 23, 42, 0.16);
      --warning-bg: #fff4db;
      --warning-border: #e7cf8c;
      --warning-text: #7a5710;
      --verify-bg: #fff9ef;
      --verify-border: #f1d9b8;
      --verify-pill-bg: #fff1d6;
      --verify-pill-text: #8a5a00;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: linear-gradient(180deg, #f8f9fc 0%, #eef2f7 100%);
      color: var(--text);
      min-height: 100vh;
    }

    .page {
      max-width: 920px;
      margin: 0 auto;
      padding: 56px 24px 120px;
    }

    .hero h1 {
      margin: 0 0 12px;
      font-size: 56px;
      line-height: 1.02;
      color: var(--red);
    }

    .hero p {
      margin: 0;
      max-width: 720px;
      font-size: 20px;
      line-height: 1.55;
      color: var(--muted);
    }

    .launcher {
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 1000;
      border: none;
      border-radius: 999px;
      background: var(--red);
      color: white;
      padding: 16px 22px;
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 16px 36px rgba(198, 40, 40, 0.3);
    }

    .launcher.hidden {
      display: none;
    }

    .launcher-icon {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: rgba(255,255,255,0.16);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: 700;
    }

    .widget {
      position: fixed;
      right: 24px;
      bottom: 24px;
      width: 420px;
      max-width: calc(100vw - 24px);
      height: 720px;
      max-height: calc(100vh - 48px);
      background: var(--card);
      border: 1px solid #eef1f5;
      border-radius: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
      display: none;
      flex-direction: column;
      z-index: 999;
    }

    .widget.open {
      display: flex;
      animation: popIn 0.18s ease;
    }

    @keyframes popIn {
      from {
        opacity: 0;
        transform: translateY(8px) scale(0.985);
      }
      to {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }

    .header {
      padding: 14px 14px 10px;
      border-bottom: 1px solid #eef1f5;
      background: #fff;
      flex-shrink: 0;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }

    .brand-mark {
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: var(--red);
      color: white;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 14px;
      flex-shrink: 0;
    }

    .brand h2 {
      margin: 0;
      font-size: 24px;
      line-height: 1.05;
      color: var(--red);
    }

    .brand p {
      margin: 3px 0 0;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.35;
    }

    .header-controls {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .lang-select {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 7px 10px;
      font-size: 13px;
      background: white;
    }

    .icon-btn {
      width: 38px;
      height: 38px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: white;
      cursor: pointer;
      font-size: 15px;
      flex-shrink: 0;
    }

    .warning {
      margin-top: 10px;
      background: var(--warning-bg);
      border: 1px solid var(--warning-border);
      color: var(--warning-text);
      border-radius: 14px;
      padding: 10px 11px;
      font-size: 12px;
      line-height: 1.4;
    }

    .quick-wrap {
      padding: 10px 12px;
      border-bottom: 1px solid #eef1f5;
      background: #fff;
      flex-shrink: 0;
      transition: all 0.2s ease;
    }

    .quick-wrap.collapsed {
      padding-top: 8px;
      padding-bottom: 8px;
    }

    .quick-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }

    .quick-title {
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
    }

    .mini-link {
      border: none;
      background: transparent;
      color: var(--red);
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      padding: 0;
    }

    .quick-grid {
      display: grid;
      gap: 8px;
      max-height: 210px;
      overflow-y: auto;
    }

    .quick-wrap.collapsed .quick-grid {
      display: none;
    }

    .quick-btn {
      width: 100%;
      border: 1px solid var(--border);
      background: #fff;
      color: var(--text);
      border-radius: 14px;
      padding: 11px 12px;
      text-align: left;
      cursor: pointer;
      font: inherit;
    }

    .quick-btn.urgent {
      background: var(--red-soft);
      border-color: #f1c3c3;
      color: var(--red);
      font-weight: 700;
    }

    .quick-btn strong {
      display: block;
      font-size: 14px;
      margin-bottom: 2px;
    }

    .quick-btn span {
      display: block;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.35;
    }

    .chat {
      flex: 1 1 auto;
      min-height: 0;
      overflow-y: auto;
      padding: 14px;
      background: #fbfbfd;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .message {
      display: flex;
    }

    .message.user {
      justify-content: flex-end;
    }

    .message.bot {
      justify-content: flex-start;
    }

    .bubble {
      max-width: 84%;
      padding: 13px 14px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.55;
      word-break: break-word;
    }

    .user .bubble {
      background: var(--red);
      color: white;
      border-bottom-right-radius: 6px;
    }

    .bot .bubble {
      background: white;
      border: 1px solid var(--border);
      border-bottom-left-radius: 6px;
    }

    .bot .bubble.error {
      border-color: #f3c2c2;
      background: #fff7f7;
    }

    .badge {
      display: inline-block;
      margin-bottom: 9px;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
    }

    .badge.hfj {
      background: var(--red-soft);
      color: var(--red);
      border: 1px solid #f1c4c4;
    }

    .badge.ai {
      background: #f3f4f6;
      color: #4b5563;
      border: 1px solid #e5e7eb;
    }

    .badge.error {
      background: #fff0f0;
      color: var(--red);
      border: 1px solid #f1c4c4;
    }

    .source {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid #eef1f4;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
    }

    .source a {
      color: var(--red);
      text-decoration: none;
      word-break: break-word;
    }

    .verify-card {
      margin-top: 12px;
      border: 1px solid var(--verify-border);
      background: var(--verify-bg);
      border-radius: 14px;
      padding: 12px;
    }

    .verify-pill {
      display: inline-block;
      margin-bottom: 8px;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      background: var(--verify-pill-bg);
      color: var(--verify-pill-text);
      border: 1px solid var(--verify-border);
    }

    .verify-title {
      font-weight: 700;
      margin-bottom: 8px;
    }

    .verify-text {
      font-size: 14px;
      line-height: 1.55;
    }

    .verify-contacts {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }

    .verify-contact {
      border: 1px solid #ecd7b2;
      background: #fffdf8;
      border-radius: 12px;
      padding: 11px;
    }

    .verify-contact-org {
      font-weight: 700;
      margin-bottom: 6px;
    }

    .verify-contact-line {
      font-size: 13px;
      line-height: 1.5;
      color: var(--text);
      margin-top: 3px;
    }

    .verify-contact-line a {
      color: var(--red);
      text-decoration: none;
      word-break: break-word;
    }

    .composer {
      border-top: 1px solid #eef1f5;
      background: white;
      padding: 12px;
      flex-shrink: 0;
    }

    .composer-row {
      display: flex;
      gap: 10px;
    }

    .composer input {
      flex: 1;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      font-size: 14px;
      outline: none;
    }

    .composer input:focus {
      border-color: var(--red);
      box-shadow: 0 0 0 3px rgba(198, 40, 40, 0.08);
    }

    .send-btn {
      border: none;
      background: var(--red);
      color: white;
      border-radius: 14px;
      padding: 0 18px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
    }

    .note {
      margin-top: 8px;
      font-size: 11px;
      color: var(--muted);
      line-height: 1.4;
    }

    .typing {
      display: flex;
      gap: 4px;
      padding-left: 8px;
    }

    .typing span {
      width: 7px;
      height: 7px;
      background: #b8bec8;
      border-radius: 50%;
      animation: bounce 1.2s infinite;
    }

    .typing span:nth-child(2) { animation-delay: 0.2s; }
    .typing span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
      40% { transform: scale(1); opacity: 1; }
    }

    @media (max-width: 640px) {
      .page {
        padding: 32px 16px 110px;
      }

      .hero h1 {
        font-size: 40px;
      }

      .hero p {
        font-size: 18px;
      }

      .widget {
        right: 10px;
        left: 10px;
        width: auto;
        height: calc(100vh - 20px);
        max-height: none;
        max-width: none;
        bottom: 10px;
      }

      .launcher {
        right: 12px;
        left: 12px;
        bottom: 12px;
        justify-content: center;
      }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1 id="heroTitle">Ask Hope</h1>
      <p id="heroText">A guided assistant for trafficking awareness, support information, and trusted next steps.</p>
    </div>
  </div>

  <div id="widget" class="widget">
    <div class="header">
      <div class="topbar">
        <div class="brand">
          <div class="brand-mark">AH</div>
          <div>
            <h2 id="widgetTitle">Ask Hope</h2>
            <p id="widgetSubtitle">Guidance, support routes, and trusted information.</p>
          </div>
        </div>
        <div class="header-controls">
          <select id="languageSelect" class="lang-select" onchange="setLanguage(this.value)">
            <option value="en">English</option>
            <option value="es">Español</option>
            <option value="auto">Auto</option>
          </select>
          <button class="icon-btn" onclick="toggleWidget(false)" title="Close">✕</button>
        </div>
      </div>

      <div class="warning" id="warningText">
        If someone is in immediate danger, contact emergency services right away. This assistant is not an emergency service.
      </div>
    </div>

    <div id="quickWrap" class="quick-wrap">
      <div class="quick-header">
        <div class="quick-title" id="quickTitle">Quick actions</div>
        <button class="mini-link" id="hideQuickText" onclick="toggleQuickActions()">Hide</button>
      </div>

      <div class="quick-grid">
        <button class="quick-btn urgent" onclick="sendPreset(translations[uiLanguage].presetDanger)">
          <span id="btnDanger">Immediate danger</span>
        </button>

        <button class="quick-btn urgent" onclick="sendPreset(translations[uiLanguage].presetNeedHelp)">
          <span id="btnNeedHelp">I need help now</span>
        </button>

        <button class="quick-btn urgent" onclick="sendPreset(translations[uiLanguage].presetWorried)">
          <span id="btnWorried">I’m worried about someone else</span>
        </button>

        <button class="quick-btn" onclick="sendPreset(translations[uiLanguage].presetWhatIs)">
          <strong id="quickWhatTitle">What is trafficking?</strong>
          <span id="quickWhatText">Understand the basics and how exploitation is defined.</span>
        </button>

        <button class="quick-btn" onclick="sendPreset(translations[uiLanguage].presetSigns)">
          <strong id="quickSignsTitle">Learn the signs</strong>
          <span id="quickSignsText">See common warning signs and indicators.</span>
        </button>
      </div>
    </div>

    <div id="chat" class="chat">
      <div class="message bot">
        <div class="bubble">
          <div class="badge hfj" id="initialBadge">Official guidance</div>
          <span id="initialMessage">
            Hello — I’m Ask Hope.<br><br>
            I can help explain trafficking-related topics, help you spot the signs, and guide you to support options based on your location.
          </span>
        </div>
      </div>
    </div>

    <div class="composer">
      <div class="composer-row">
        <input id="input" type="text" placeholder="Ask a question..." />
        <button class="send-btn" id="sendButton" onclick="sendMessage()">Send</button>
      </div>
      <div class="note" id="composerNote">
        This assistant provides information and support guidance. It is not an emergency service.
      </div>
    </div>
  </div>

  <button id="launcher" class="launcher" onclick="toggleWidget(true)">
    <span class="launcher-icon">?</span>
    <span id="launcherText">Ask Hope</span>
  </button>

  <script>
    const API_URL = "https://hfj-assistant.onrender.com/chat";
    let sessionId = localStorage.getItem("askhope_session_id") || null;
    let uiLanguage = localStorage.getItem("askhope_language") || "auto";
    window.pendingAdditionalContacts = null;

    const translations = {
      en: {
        heroText: "A guided assistant for trafficking awareness, support information, and trusted next steps.",
        widgetSubtitle: "Guidance, support routes, and trusted information.",
        warning: "If someone is in immediate danger, contact emergency services right away. This assistant is not an emergency service.",
        quickTitle: "Quick actions",
        hide: "Hide",
        btnDanger: "Immediate danger",
        btnNeedHelp: "I need help now",
        btnWorried: "I’m worried about someone else",
        quickWhatTitle: "What is trafficking?",
        quickWhatText: "Understand the basics and how exploitation is defined.",
        quickSignsTitle: "Learn the signs",
        quickSignsText: "See common warning signs and indicators.",
        initialBadge: "Official guidance",
        initialMessage: "Hello — I’m Ask Hope.<br><br>I can help explain trafficking-related topics, help you spot the signs, and guide you to support options based on your location.",
        inputPlaceholder: "Ask a question...",
        send: "Send",
        composerNote: "This assistant provides information and support guidance. It is not an emergency service.",
        launcher: "Ask Hope",
        sources: "Sources:",
        verify: "Additional local contacts — please verify",
        connectionIssue: "Connection issue",
        presetDanger: "I am in immediate danger and need help",
        presetNeedHelp: "I think I am being trafficked and need help",
        presetWorried: "I think someone else may be being trafficked",
        presetWhatIs: "What is human trafficking?",
        presetSigns: "How do I spot the signs of trafficking?",
        errorResponse: "I couldn’t complete that request just now:",
        cannotUnderstand: "I couldn’t understand the response from the assistant.",
        troubleConnecting: "I’m having trouble connecting right now. Please try again in a moment.",
        fallbackContact: "Local support contact",
        labelPhone: "Phone:",
        labelHours: "Hours:",
        labelWebsite: "Website:",
        labelEmail: "Email:",
        labelNotes: "Notes:",
        noContacts: "No additional local contacts were available."
      },
      es: {
        heroText: "Un asistente guiado para la concienciación sobre la trata, información de apoyo y próximos pasos de confianza.",
        widgetSubtitle: "Orientación, rutas de apoyo e información de confianza.",
        warning: "Si alguien está en peligro inmediato, contacta de inmediato con los servicios de emergencia. Este asistente no es un servicio de emergencia.",
        quickTitle: "Acciones rápidas",
        hide: "Ocultar",
        btnDanger: "Peligro inmediato",
        btnNeedHelp: "Necesito ayuda ahora",
        btnWorried: "Me preocupa otra persona",
        quickWhatTitle: "¿Qué es la trata?",
        quickWhatText: "Comprende lo básico y cómo se define la explotación.",
        quickSignsTitle: "Conoce las señales",
        quickSignsText: "Consulta señales de alerta e indicadores comunes.",
        initialBadge: "Orientación oficial",
        initialMessage: "Hola — soy Ask Hope.<br><br>Puedo ayudarte a entender temas relacionados con la trata, identificar señales de alerta y orientarte hacia opciones de apoyo según tu ubicación.",
        inputPlaceholder: "Escribe tu pregunta...",
        send: "Enviar",
        composerNote: "Este asistente ofrece información y orientación de apoyo. No es un servicio de emergencia.",
        launcher: "Ask Hope",
        sources: "Fuentes:",
        verify: "Contactos locales adicionales — por favor verifícalos",
        connectionIssue: "Problema de conexión",
        presetDanger: "Estoy en peligro inmediato y necesito ayuda",
        presetNeedHelp: "Creo que estoy siendo víctima de trata y necesito ayuda",
        presetWorried: "Creo que otra persona puede estar siendo víctima de trata",
        presetWhatIs: "¿Qué es la trata de personas?",
        presetSigns: "¿Cómo puedo identificar las señales de trata?",
        errorResponse: "No pude completar esa solicitud en este momento:",
        cannotUnderstand: "No pude entender la respuesta del asistente.",
        troubleConnecting: "Tengo problemas para conectarme en este momento. Por favor, inténtalo de nuevo en un momento.",
        fallbackContact: "Contacto de apoyo local",
        labelPhone: "Teléfono:",
        labelHours: "Horario:",
        labelWebsite: "Sitio web:",
        labelEmail: "Correo electrónico:",
        labelNotes: "Notas:",
        noContacts: "No había contactos locales adicionales disponibles."
      },
      auto: {}
    };

    function currentTextLanguage() {
      return uiLanguage === "auto" ? "en" : uiLanguage;
    }

    function applyTranslations() {
      const t = translations[currentTextLanguage()];
      document.getElementById("heroText").textContent = t.heroText;
      document.getElementById("widgetSubtitle").textContent = t.widgetSubtitle;
      document.getElementById("warningText").textContent = t.warning;
      document.getElementById("quickTitle").textContent = t.quickTitle;
      document.getElementById("hideQuickText").textContent = t.hide;
      document.getElementById("btnDanger").textContent = t.btnDanger;
      document.getElementById("btnNeedHelp").textContent = t.btnNeedHelp;
      document.getElementById("btnWorried").textContent = t.btnWorried;
      document.getElementById("quickWhatTitle").textContent = t.quickWhatTitle;
      document.getElementById("quickWhatText").textContent = t.quickWhatText;
      document.getElementById("quickSignsTitle").textContent = t.quickSignsTitle;
      document.getElementById("quickSignsText").textContent = t.quickSignsText;
      document.getElementById("input").placeholder = t.inputPlaceholder;
      document.getElementById("sendButton").textContent = t.send;
      document.getElementById("composerNote").textContent = t.composerNote;
      document.getElementById("launcherText").textContent = t.launcher;
      document.getElementById("initialBadge").textContent = t.initialBadge;
      document.getElementById("initialMessage").innerHTML = t.initialMessage;
      document.getElementById("languageSelect").value = uiLanguage;
    }

    function setLanguage(lang) {
      uiLanguage = lang;
      localStorage.setItem("askhope_language", lang);
      applyTranslations();
    }

    function toggleWidget(forceState = null) {
      const widget = document.getElementById("widget");
      const launcher = document.getElementById("launcher");

      const shouldOpen = forceState === null
        ? !widget.classList.contains("open")
        : forceState;

      if (shouldOpen) {
        widget.classList.add("open");
        launcher.classList.add("hidden");
        setTimeout(() => document.getElementById("input").focus(), 60);
      } else {
        widget.classList.remove("open");
        launcher.classList.remove("hidden");
      }
    }

    function toggleQuickActions() {
      const wrap = document.getElementById("quickWrap");
      wrap.classList.toggle("collapsed");
    }

    function collapseQuickActions() {
      const wrap = document.getElementById("quickWrap");
      if (!wrap.classList.contains("collapsed")) {
        wrap.classList.add("collapsed");
      }
    }

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }

    function renderSources(source, extraSources = []) {
      const links = [];
      const t = translations[currentTextLanguage()];

      if (source && source !== "AI-generated general guidance") {
        const safeSource = escapeHtml(source);
        links.push(`<a href="${safeSource}" target="_blank" rel="noopener noreferrer">${safeSource}</a>`);
      }

      extraSources.forEach((item) => {
        const safeItem = escapeHtml(item);
        links.push(`<a href="${safeItem}" target="_blank" rel="noopener noreferrer">${safeItem}</a>`);
      });

      if (!links.length) return "";
      return `<div class="source">${t.sources}<br>${links.join("<br>")}</div>`;
    }

    function renderAdditionalContactsCard(extra) {
      const t = translations[currentTextLanguage()];
      const safeTitle = escapeHtml(extra.title || (currentTextLanguage() === "es" ? "Contactos locales adicionales" : "Additional local contacts"));
      const safeStatus = escapeHtml(extra.status || "verify");
      const contacts = Array.isArray(extra.contacts) ? extra.contacts : [];
      const rawText = extra.raw_text || "";

      let bodyHtml = "";

      if (contacts.length) {
        const cards = contacts.map(contact => {
          const organisation = escapeHtml(contact.organisation || t.fallbackContact);
          const phone = escapeHtml(contact.phone || "");
          const hours = escapeHtml(contact.hours || "");
          const website = escapeHtml(contact.website || "");
          const email = escapeHtml(contact.email || "");
          const notes = escapeHtml(contact.notes || "");

          return `
            <div class="verify-contact">
              <div class="verify-contact-org">${organisation}</div>
              ${phone ? `<div class="verify-contact-line"><strong>${t.labelPhone}</strong> ${phone}</div>` : ""}
              ${hours ? `<div class="verify-contact-line"><strong>${t.labelHours}</strong> ${hours}</div>` : ""}
              ${website ? `<div class="verify-contact-line"><strong>${t.labelWebsite}</strong> <a href="${website}" target="_blank" rel="noopener noreferrer">${website}</a></div>` : ""}
              ${email ? `<div class="verify-contact-line"><strong>${t.labelEmail}</strong> ${email}</div>` : ""}
              ${notes ? `<div class="verify-contact-line"><strong>${t.labelNotes}</strong> ${notes}</div>` : ""}
            </div>
          `;
        }).join("");

        bodyHtml = `<div class="verify-contacts">${cards}</div>`;
      } else if (rawText) {
        bodyHtml = `<div class="verify-text">${escapeHtml(rawText).replace(/\n/g, "<br>")}</div>`;
      } else {
        bodyHtml = `<div class="verify-text">${t.noContacts}</div>`;
      }

      return `
        <div class="verify-card">
          <div class="verify-pill">
            ${safeStatus === "verify" ? t.verify : safeStatus}
          </div>
          <div class="verify-title">${safeTitle}</div>
          ${bodyHtml}
        </div>
      `;
    }

    function appendMessage(role, text, source = null, type = null, extraSources = [], isError = false) {
      const chatBox = document.getElementById("chat");
      const t = translations[currentTextLanguage()];
      const safeText = escapeHtml(text).replace(/\n/g, "<br>");

      let badgeHtml = "";
      let errorClass = "";

      if (isError) {
        badgeHtml = `<div class="badge error">${t.connectionIssue}</div>`;
        errorClass = "error";
      } else if (role === "bot" && type === "hfj") {
        badgeHtml = `<div class="badge hfj">${currentTextLanguage() === "es" ? "Orientación oficial" : "Official guidance"}</div>`;
      } else if (role === "bot" && type === "ai") {
        badgeHtml = `<div class="badge ai">${currentTextLanguage() === "es" ? "Orientación general" : "General guidance"}</div>`;
      }

      const sourceHtml = role === "bot" && !isError ? renderSources(source, extraSources) : "";

      let extraCardHtml = "";

      if (role === "bot" && window.pendingAdditionalContacts) {
        extraCardHtml = renderAdditionalContactsCard(window.pendingAdditionalContacts);
        window.pendingAdditionalContacts = null;
      }

      const html = `
        <div class="message ${role}">
          <div class="bubble ${errorClass}">
            ${badgeHtml}
            ${safeText}
            ${sourceHtml}
            ${extraCardHtml}
          </div>
        </div>
      `;

      chatBox.insertAdjacentHTML("beforeend", html);
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    function sendPreset(text) {
      toggleWidget(true);
      document.getElementById("input").value = text;
      sendMessage();
    }

    async function sendMessage() {
      const input = document.getElementById("input");
      const chatBox = document.getElementById("chat");
      const t = translations[currentTextLanguage()];
      const message = input.value.trim();

      if (!message) return;

      collapseQuickActions();
      appendMessage("user", message);
      input.value = "";

      const typingId = "typing-" + Date.now();
      chatBox.insertAdjacentHTML(
        "beforeend",
        `<div id="${typingId}" class="typing"><span></span><span></span><span></span></div>`
      );
      chatBox.scrollTop = chatBox.scrollHeight;

      try {
        const requestLanguage = uiLanguage === "auto" ? null : uiLanguage;

        const response = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            session_id: sessionId,
            language: requestLanguage
          })
        });

        const rawText = await response.text();
        let data = {};

        try {
          data = JSON.parse(rawText);
        } catch (e) {
          throw new Error(`Non-JSON response: ${rawText}`);
        }

        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        if (data.session_id) {
          sessionId = data.session_id;
          localStorage.setItem("askhope_session_id", sessionId);
        }

        if (uiLanguage === "auto" && data.language && (data.language === "en" || data.language === "es")) {
          // only use for rendering dynamic labels during this response
        }

        window.pendingAdditionalContacts = null;

        if (data.additional_contacts_title || data.additional_contacts || data.additional_contacts_raw_text) {
          window.pendingAdditionalContacts = {
            title: data.additional_contacts_title,
            status: data.additional_contacts_status,
            contacts: data.additional_contacts || [],
            raw_text: data.additional_contacts_raw_text || ""
          };
        }

        if (data.reply) {
          appendMessage("bot", data.reply, data.source, data.type, data.extra_sources || []);
        } else if (data.detail) {
          appendMessage(
            "bot",
            `${t.errorResponse} ${data.detail}`,
            null,
            null,
            [],
            true
          );
        } else {
          appendMessage(
            "bot",
            t.cannotUnderstand,
            null,
            null,
            [],
            true
          );
        }
      } catch (error) {
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        appendMessage(
          "bot",
          t.troubleConnecting,
          null,
          null,
          [],
          true
        );
      }
    }

    document.getElementById("input").addEventListener("keypress", function(event) {
      if (event.key === "Enter") {
        sendMessage();
      }
    });

    applyTranslations();
  </script>
</body>
</html>
