# CyberPravoBot 🛡️

An advanced, asynchronous, AI-powered Anti-Phishing and CyberSecurity Telegram bot designed to analyze text messages, intercept social engineering vectors, and verify suspicious URLs in real-time.

---

## 🚀 Architectural Overview

`CyberPravoBot` operates as an intelligent multi-layered security shield. Instead of depending entirely on static blacklists, the system utilizes high-speed LLM inference combined with dynamic contextual scanning presets to dissect malicious intents (e.g., fraudulent listings, banking scams, credential harvesting).

### Key Technical Capabilities:
* **Multi-Model AI Infrastructure:** Features a dynamic backend router that allows real-time hot-swapping between three distinct Large Language Models via a secured administrator dashboard.
* **Asynchronous High-Performance Database:** Built with `aiosqlite` to log user interaction telemetry, execute analytical regex data-mining, and manage state transitions natively without blocking the primary event loop.
* **VirusTotal API v3 Threat Intelligence:** Integrated asynchronous URL scanner that base64-encodes links, checks global malware flags, and natively injects diagnostic reports directly into the AI's cognitive prompt context.
* **Clean Architecture & Internationalization:** Deep isolation of UI components, specialized system prompts, and configuration variables (`config.py`) ensures modular scalability and easy localization.

---

## 📸 Demonstration

![CyberPravoBot Operational Preview](assets/demo.gif)

---

## 🧠 Supported AI Engine Configurations

The core routing layer natively interfaces with the Groq API infrastructure, running optimized system prompts across three target model configurations:

1. **Llama 70B (Standard Mode) 🛡️**
   * **Target Model Identifier:** `llama-3.3-70b-versatile`
   * **Application:** Balanced, everyday threat assessment, text pattern matching, and standard linguistic validation.

2. **GPT 120B (Ultra Mode) 🧠**
   * **Target Model Identifier:** `openai/gpt-oss-120b`
   * **Application:** Heavy multi-factor cognitive audits, internal base64/hex string decoding, and complex social engineering detection.

3. **Llama 17B (Mass Mode) ⚡**
   * **Target Model Identifier:** `meta-llama/llama-4-scout-17b-16e-instruct`
   * **Application:** Lightweight, low-latency concurrent processing, rapid scanning of text blocks under high traffic conditions.

---

## 🛠️ Complete Technical Stack

* **Language:** Python 3.10+
* **Framework:** Aiogram 3.x (Asynchronous Telegram Bot API wrapper)
* **AI Client:** Groq Async SDK
* **Network Layer:** aiohttp (Asynchronous HTTP Client for VirusTotal integrations)
* **Database Driver:** aiosqlite (Non-blocking SQLite wrapper layer)
* **Environment Controller:** python-dotenv

---

## 💻 Environment Setup & Deployment

1. **Clone the project infrastructure:**
   ```bash
   git clone [https://github.com/egraich/CyberPravoBot.git](https://github.com/egraich/CyberPravoBot.git)
   cd CyberPravoBot
   ```

2. **Establish Secure Configurations:**
   Generate a local .env configuration payload inside the root directory:
   ```
   BOT_TOKEN=your_telegram_bot_token_here
   ADMIN_ID=your_numerical_telegram_user_id
   AI_KEY=your_groq_api_key_credentials
   VT_API_KEY=your_virustotal_v3_api_key
   ```

3. Initialize Core Modules:
   ```
   python main.py
   ```

## 📜 Open Source Licensing

This software architecture is fully distributed under the **MIT License**.

```
Copyright (c) 2026 @egraich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons...
```

For comprehensive compliance guidelines, see the accompanying LICENSE file.

Maintained with ❤️ by @egraich