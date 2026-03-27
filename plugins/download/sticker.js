// © 2026 arun•°Cumar. All Rights Reserved.
import { downloadContentFromMessage } from '@whiskeysockets/baileys';
import { toSticker } from '../../lib/emix.js'; 

export default async (sock, msg) => {
    const from = msg.key.remoteJid;
    

    const type = Object.keys(msg.message || {})[0];
    const quoted = msg.message?.[type]?.contextInfo?.quotedMessage;
    const quotedType = quoted ? Object.keys(quoted)[0] : null;
    
    const isImage = type === 'imageMessage' || quotedType === 'imageMessage';
    const isVideo = type === 'videoMessage' || quotedType === 'videoMessage';

    if (isImage || isVideo) {
        try {
            await sock.sendMessage(from, { text: '⏳ Creating sticker...' });

            const mediaObj = quoted ? quoted[quotedType] : msg.message[type];
            const mediaType = isImage ? 'image' : 'video';
            const ext = isImage ? 'jpg' : 'mp4'; 

            const stream = await downloadContentFromMessage(mediaObj, mediaType);
            let buffer = Buffer.from([]);
            for await (const chunk of stream) {
                buffer = Buffer.concat([buffer, chunk]);
            }

            const sticker = await toSticker(buffer, ext); 

            await sock.sendMessage(from, { sticker: sticker });

        } catch (err) {
            console.error("Sticker Error:", err);
            await sock.sendMessage(from, { text: '❌ Error: Failed to process media.' });
        }
    } else {
        await sock.sendMessage(from, { text: '❌ Please reply to an image or short video with .sticker' });
    }
};
