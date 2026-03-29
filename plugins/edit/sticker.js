import { createSticker } from "../../lib/store/sticker.js";

export default async (sock, msg, args) => {
    const chat = msg.key.remoteJid;

    try {
        const stickerBuffer = await createSticker(sock, msg);

        if (!stickerBuffer) {
            return sock.sendMessage(chat, { 
                text: "* Nexa-Bot MD STICKER ENGINE*\n\nReply to an image/video/gif." 
            }, { quoted: msg });
        }

        await sock.sendMessage(chat, { react: { text: "🎨", key: msg.key } });

        await sock.sendMessage(chat, { sticker: stickerBuffer }, { quoted: msg });

    } catch (error) {
        console.error(error);
        await sock.sendMessage(chat, { text: "❌ Failed to create sticker." });
    }
};
