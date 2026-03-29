// © 2026 arun•°Cumar. All Rights Reserved.
import fs from 'fs';
import { downloadYt } from '../../lib/store/download/ytvideo.js';

export default async (sock, msg, args) => {
    const from = msg.key.remoteJid;

    if (!args[0]) {
        return sock.sendMessage(from, { text: "Provide a YouTube link!" });
    }

    try {
        await sock.sendMessage(from, { react: { text: '⏳', key: msg.key } });

        const filePath = await downloadYt(args[0], 'video');

        await sock.sendMessage(from, {
            video: { url: filePath },
            caption: "🎬 Nexa-Bot Downloader"
        }, { quoted: msg });

        fs.unlinkSync(filePath);

        await sock.sendMessage(from, { react: { text: '✅', key: msg.key } });

    } catch (e) {
        console.log(e);
        await sock.sendMessage(from, {
            text: "❌ Download failed."
        });
    }
};
