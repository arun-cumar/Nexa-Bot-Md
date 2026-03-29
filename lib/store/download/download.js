import { downloadContentFromMessage } from '@whiskeysockets/baileys';

export const downloadMedia = async (message) => {
    let type = Object.keys(message)[0];
    let msgContent = message[type];

    // View once fix
    if (type === 'viewOnceMessageV2' || type === 'viewOnceMessage') {
        msgContent = msgContent.message;
        type = Object.keys(msgContent)[0];
        msgContent = msgContent[type];
    }

    const mimeMap = {
        imageMessage: 'image',
        videoMessage: 'video',
        audioMessage: 'audio',
        stickerMessage: 'sticker',
        documentMessage: 'document'
    };

    const downloadType = mimeMap[type];
    if (!downloadType) throw new Error("Unsupported media type");

    const stream = await downloadContentFromMessage(msgContent, downloadType);
    let buffer = Buffer.from([]);

    for await (const chunk of stream) {
        buffer = Buffer.concat([buffer, chunk]);
    }

    return buffer;
};
