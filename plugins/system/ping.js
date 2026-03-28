import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getRandomPing } from '../../lib/nexa/ping.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default async (sock, msg, args) => {
    const chat = msg.key.remoteJid;

    // Correct image path
    const imagePath = path.join(__dirname, '../../media/nexa.jpg');

    try {
        await sock.sendMessage(chat, { react: { text: "📡", key: msg.key } });

        await sock.sendMessage(chat, { text: "🚀 Connecting to NEXA-BOT Server..." });

        const pingValue = Math.abs(Date.now() - (msg.messageTimestamp * 1000));
        const speedStatus = pingValue < 500 ? "Turbo 🚀" : "Normal ⚡";
        const netStatus = "🟢 High Speed";

        const pingMsg = getRandomPing(pingValue, speedStatus, netStatus);

        if (fs.existsSync(imagePath)) {
            await sock.sendMessage(chat, {
                image: fs.readFileSync(imagePath),
                caption: pingMsg
            }, { quoted: msg });
        } else {
            await sock.sendMessage(chat, {
                text: pingMsg
            }, { quoted: msg });
        }

    } catch (e) {
        console.error("Ping Error:", e);
    }
};
