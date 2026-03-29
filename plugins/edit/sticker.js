// © 2026 arun•°Cumar. All Rights Reserved.
import { imageToSticker, videoToSticker, gifToSticker } from '../../lib/store/emix.js';
import { downloadMedia } from '../../lib/store/download/download.js';

export default async (sock, msg, args) => {
    const from = msg.key.remoteJid;

    try {
        const quotedMsg = msg.message?.extendedTextMessage?.contextInfo?.quotedMessage;

        if (!quotedMsg) {
            return await sock.sendMessage(from, {
                text: "Reply to image/video/gif to make sticker!"
            }, { quoted: msg });
        }

        // Download media buffer
        const buffer = await downloadMedia(quotedMsg);

        // Detect type
        const type = Object.keys(quotedMsg)[0];

        if (type === 'imageMessage') {
            const sticker = await imageToSticker(buffer, 'jpg');
            await sock.sendMessage(from, { sticker: sticker }, { quoted: msg });
        }
        else if (type === 'videoMessage') {
            if (quotedMsg.videoMessage?.gifPlayback) {
                const sticker = await gifToSticker(buffer, 'mp4');
                await sock.sendMessage(from, { sticker: sticker }, { quoted: msg });
            } else {
                const sticker = await videoToSticker(buffer, 'mp4');
                await sock.sendMessage(from, { sticker: sticker }, { quoted: msg });
            }
        }
        else {
            await sock.sendMessage(from, {
                text: "Only image/video/gif supported!"
            }, { quoted: msg });
        }

    } catch (err) {
        console.log("Sticker Error:", err);
        await sock.sendMessage(from, {
            text: "❌ Sticker conversion failed!"
        }, { quoted: msg });
    }
};
