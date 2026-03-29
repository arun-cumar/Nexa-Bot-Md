import { makeSticker } from '../../lib/store/emix.js';

export default async (sock, msg, args) => {
    const chat = msg.key.remoteJid;

    try {
        const stickerBuffer = await makeSticker(msg);

        if (!stickerBuffer) {
            return sock.sendMessage(chat, {
                text: "*Reply to an image, video or GIF with .sticker*"
            }, { quoted: msg });
        }

        await sock.sendMessage(chat, {
            react: { text: "🎨", key: msg.key }
        });

        await sock.sendMessage(chat, {
            sticker: stickerBuffer
        }, { quoted: msg });

    } catch (e) {
        console.log(e);
        await sock.sendMessage(chat, {
            text: "❌ Sticker failed"
        });
    }
};
