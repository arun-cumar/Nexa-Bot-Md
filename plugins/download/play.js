// © 2026 arun•°Cumar. All Rights Reserved.
import { ytPlay } from '../../lib/store/download/ytplay.js';

export default async (sock, msg, args) => {
    const from = msg.key.remoteJid;

    if (!args.length) {
        return sock.sendMessage(from, {
            text: "🎵 Example: .play Believer"
        }, { quoted: msg });
    }

    try {
        await sock.sendMessage(from, {
            text: "🔍 Searching song..."
        }, { quoted: msg });

        const query = args.join(" ");
        const data = await ytPlay(query);

        const title = data.title || "Unknown";
        const videoUrl = data.video || data.videoUrl || data.url;
        const audioUrl = data.audio || data.audioUrl;

        let caption = `🎵 *${title}*\n\n⬇️ Downloaded via Nexa-Bot`;

        if (audioUrl) {
            await sock.sendMessage(from, {
                audio: { url: audioUrl },
                mimetype: 'audio/mpeg'
            }, { quoted: msg });
        } else if (videoUrl) {
            await sock.sendMessage(from, {
                video: { url: videoUrl },
                caption: caption
            }, { quoted: msg });
        } else {
            throw new Error("No media URL found");
        }

    } catch (e) {
        console.log("Play Error:", e);
        await sock.sendMessage(from, {
            text: "❌ Song not found or API down."
        }, { quoted: msg });
    }
};
