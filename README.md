# CyberPravoBot 🛡️

![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white) &nbsp; ![Aiogram](https://img.shields.io/badge/framework-aiogram_3.x-green?style=flat-square&logo=telegram&logoColor=white) &nbsp; ![License](https://img.shields.io/badge/license-MIT-red?style=flat-square)

An asynchronous Telegram bot powered by LLMs and threat intelligence to detect phishing, social engineering, and malicious URLs in real-time.

> 💡 **The Backstory:** 
> This project was built for the republican cyber-security competition [**#КиберПраво** (#CyberLaw)](https://a1.by/ru/company/news/pri-podderzhke-a1-v-belarusi-zapustili-konkurs-kiberpravo-dlya-detej-i-podrostkov/p/kiberpravo). Due to a bureaucratic mess at the school level, my official application was lost, and the bot never reached the jury — stripping me of the chance to fight for the grand prize.
> 
> Instead of letting a production-ready Telegram bot sit in a private folder, I am releasing it to the world. This code is a personal statement by [egraich](https://github.com/egraich) as an independent developer. Use it, fork it, and build something better.

---

## ⚙️ System Overview

`CyberPravoBot` acts as an automated security filter for text messages and links. Instead of relying solely on static blacklists, the bot analyzes incoming text dynamically using LLMs to recognize fraudulent context, banking scams, and credential harvesting attempts.

### Core Technical Features:
* **Dynamic LLM Routing:** A backend router that allows real-time hot-swapping between three different model configurations via an administrator dashboard.
* **Asynchronous Architecture:** Built on top of `aiogram` and `aiosqlite` to log interaction telemetry and handle database operations natively without blocking the primary event loop.
* **VirusTotal API v3 Integration:** Automatically extracts and base64-encodes URLs to check them against global threat intelligence data, appending safety reports directly to the LLM prompt for precise analysis.
* **Modular Codebase:** Strict separation of UI handlers, database logic, and system prompts with centralized management via `config.py`.

---

## 📸 Demonstration

<video src="https://github.com/user-attachments/assets/3606ac11-001e-45e8-b746-acc80d5a2bcc" autoplay loop muted playsinline width="100%" style="pointer-events: none;"></video>

---

## 🧠 Supported Model Configurations

The routing layer connects to the Groq API infrastructure and dynamically selects system prompt presets depending on the selected model:

1. **Llama 70B (Standard Mode) 🛡️**
   * **Model ID:** `llama-3.3-70b-versatile`
   * **Use Case:** Default threat assessment, general text classification, and pattern matching.

2. **GPT Engine (Ultra Mode) 🧠**
   * **Model ID:** `openai/gpt-oss-120b`
   * **Use Case:** Deep contextual analysis, decoding suspicious strings (base64/hex), and advanced social engineering detection.

3. **Llama 17B (Mass Mode) ⚡**
   * **Model ID:** `meta-llama/llama-4-scout-17b-16e-instruct`
   * **Use Case:** High-throughput, low-latency text scanning under heavy concurrent traffic.

---

## 🛠️ Tech Stack

* **Core:** Python 3.10+
* **Bot Framework:** Aiogram 3.x (Async Telegram Bot API)
* **AI Integration:** Groq Async SDK
* **Network:** aiohttp (Async HTTP client for VirusTotal API calls)
* **Database:** aiosqlite (Asynchronous SQLite wrapper)
* **Environment:** python-dotenv

---

## 💻 Setup & Deployment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/egraich/CyberPravoBot
   cd CyberPravoBot

   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   ADMIN_ID=your_numerical_telegram_user_id
   GROQ_API_KEY=your_groq_api_key_credentials
   VT_API_KEY=your_virustotal_v3_api_key
   ```

4. **Run the bot:**
   ```bash
   python main.py
   ```

---

## 📜 Open Source Licensing

This project is open-source and distributed under the **MIT License**. 

For details on usage permissions and liability limitations, please refer to the [LICENSE](LICENSE) file in the root directory.

Maintained with ❤️ by [@egraich](https://github.com/egraich)