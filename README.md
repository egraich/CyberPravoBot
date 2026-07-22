# CyberPravoBot

![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white) &nbsp; ![Aiogram](https://img.shields.io/badge/framework-aiogram_3.x-green?style=flat-square&logo=telegram&logoColor=white) &nbsp; ![License](https://img.shields.io/badge/license-MIT-red?style=flat-square)

An asynchronous Telegram bot that checks links and messages to protect users from scam messages.

<p align="center">
  <a href="https://github.com/user-attachments/assets/3606ac11-001e-45e8-b746-acc80d5a2bcc">
    <img width="1920" height="1080" alt="preview" src="https://github.com/user-attachments/assets/276dc486-61d3-40a4-8e70-aa92b058f8d8" />
  </a>
</p>

**[Try the Live 24/7 Telegram Bot Here](https://t.me/cyberpravobot)**

---

## Quick start

1. Go to [Chat with bot in telegram](https://t.me/cyberpravobot)
2. Press start (type `/start` if there is no button)
3. Select analysis mode (or skip it for standard mode)
4. Forward some suspicious message to it
5. Enjoy the risk score as a percentage!

---

## Features

* **Phishing Detection:** The bot detects links in messages and checks them via VirusTotal.
* **Scam Recognition:** Uses AI to read chat messages and catch scam context.
* **Admin Panel:** You can switch between 3 different AI models on the fly without turning off the bot.
* **Fast and Async:** Built to handle high load without lags by using async functions.

---

## Localization 

Because this bot was originally made for a Belarusian competition, the default UI is in Russian. However, you can easily localize everything to your own language right inside the `config.py` file.

---

## How it works

I chose **aiogram** and **aiosqlite** to make the bot completely asynchronous. This is important because API requests delay shouldn't freeze the main bot loop when checking links.

For security checks, the bot takes a URL, converts it to base64, and sends it to **VirusTotal**. After getting the answer, the bot appends this data directly into the **Groq LLM** prompt. This helps the AI make a very precise decision about whether the link is a scam or not.

For 24/7 availability, the bot is containerized with Docker and deployed on a [Hack Club Nest](https://nest.hackclub.com/) Debian server.

### Tech Stack:
* Python 3.10+
* Aiogram 3.x (Bot framework)
* Groq SDK & aiohttp (For AI and VirusTotal API)
* aiosqlite (Database)

---

## How to Run Locally

### Requirements
* Python 3.10 or higher
* VirusTotal API Key and Groq API Key
* All from requirements.txt ¯\\_(ツ)_/¯

### Setup Steps
1. **Clone the project:**
   ```bash
   git clone https://github.com/egraich/CyberPravoBot
   cd CyberPravoBot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create Environment Variables:**
   Create a `.env` file in the root folder and add your keys:
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

## Deployment

If you want to host this bot on your own Linux server, you can set it up with Docker Compose by instructions below:

### Prerequisites
Ensure your server has Docker and Docker Compose installed.

### Installation Steps

1. **Navigate to your workspace directory:**
   ```bash
   cd /path/to/your/projects
   ```

2. **Clone the repository:**
   ```bash
   git clone https://github.com/egraich/CyberPravoBot
   ```

3. **Rename repository for database isolation:**
   ```bash
   mv CyberPravoBot src
   ```

4. **Configure Environment Variables:**
   Create and fill a `.env` file **outside** the `src/` directory to protect your credentials:
   ```bash
   nano .env
   ```
   *Paste your keys as described in the local configuration section.*

5. **Launch the Container:**
   Navigate into the code directory and boot up the application:
   ```bash
   cd src
   docker compose up -d --build
   ```
   >(Note: Use `docker-compose up -d --build` if your server uses Docker Compose v1).

---

## The Backstory

I originally built this bot for a big cyber-security competition in Belarus called [#КиберПраво(#CyberLaw)](https://a1.by/ru/company/news/pri-podderzhke-a1-v-belarusi-zapustili-konkurs-kiberpravo-dlya-detej-i-podrostkov/p/kiberpravo). But because of a bureaucratic mistake at my school, my official papers were lost, and my bot never reached the judges. I didn't want to delete a fully working project, so I polished the code and released it here for everyone.

---

## License
This project is open-source under the MIT License. 

Made by [egraich](https://github.com/egraich)
