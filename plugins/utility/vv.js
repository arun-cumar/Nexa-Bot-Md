// © 2026 arun•°Cumar
import { downloadMedia } from '../../lib/store/download/download.js';
import { toViewOncePhoto, toViewOnceVideo, toViewOnceVoice } from '../../lib/store/emix.js';

export default async (sock, msg, args) => {
    const from = msg.key.remoteJid;

    try {
        const quoted =
            msg.message?.extendedTextMessage?.contextInfo?.quotedMessage ||
            msg.message?.imageMessage?.contextInfo?.quotedMessage ||
            msg.message?.videoMessage?.contextInfo?.quotedMessage;

        if (!quoted) {
            return sock.sendMessage(from, {
                text: "📌 Reply to a media message"
            }, { quoted: msg });
        }

        const { buffer, type, msgContent } = await downloadMedia(quoted);

        const caption = msgContent?.caption || "";

        let viewOnceContent;

        if (type === 'imageMessage') {
            viewOnceContent = toViewOncePhoto(buffer, caption);
        } else if (type === 'videoMessage') {
            viewOnceContent = toViewOnceVideo(buffer, caption);
        } else if (type === 'audioMessage') {
            viewOnceContent = toViewOnceVoice(buffer);
        } else {
            return sock.sendMessage(from, {
                text: "❌ Unsupported media"
            }, { quoted: msg });
        }

        await sock.sendMessage(from, {
            viewOnceMessage: {
                message: viewOnceContent
            }
        }, { quoted: msg });

    } catch (err) {
        console.error("VV Error:", err);

        await sock.sendMessage(from, {
            text: "❌ Failed to process view-once"
        }, { quoted: msg });
    }
};
