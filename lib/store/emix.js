import { Sticker, StickerTypes } from 'wa-sticker-formatter';
import { downloadContentFromMessage } from "@whiskeysockets/baileys";

export async function createSticker(sock, msg) {
    try {
    
        const quoted = msg.message?.extendedTextMessage?.contextInfo?.quotedMessage;
        let mediaMessage;
        let type;

        if (quoted) {
            type = Object.keys(quoted)[0];
            mediaMessage = quoted[type];
            if (type === 'viewOnceMessageV2') {
                mediaMessage = quoted.viewOnceMessageV2.message.imageMessage || quoted.viewOnceMessageV2.message.videoMessage;
            }
        } else {
            type = Object.keys(msg.message || {})[0];
            mediaMessage = msg.message?.[type];
        }

        if (!mediaMessage || !mediaMessage.mimetype) return null;

        const isVideo = mediaMessage.mimetype.includes('video') || mediaMessage.mimetype.includes('gif');
        const downloadType = mediaMessage.mimetype.includes('video') ? 'video' : 'image';


        const stream = await downloadContentFromMessage(mediaMessage, downloadType);
        let buffer = Buffer.from([]);
        for await (const chunk of stream) {
            buffer = Buffer.concat([buffer, chunk]);
        }


        const sticker = new Sticker(buffer, {
            pack: ' Nexa-Bot MD Pack ',
            author: 'Arun Cumar',
            type: StickerTypes.FULL,
            categories: ['🔥'],
            quality: isVideo ? 10 : 50 
        });

        return await sticker.toBuffer();

    } catch (err) {
        console.error("Sticker Engine Error:", err);
        return null;
    }
}

