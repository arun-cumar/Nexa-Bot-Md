import fs from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegPath from 'ffmpeg-static';
import { Sticker, StickerTypes } from 'wa-sticker-formatter';
import { downloadContentFromMessage } from '@whiskeysockets/baileys';

export const downloadViewOnceMedia = async (msg) => {
    const quoted = msg.message?.extendedTextMessage?.contextInfo;

    if (!quoted || !quoted.quotedMessage) {
        return null;
    }

    let qMsg = quoted.quotedMessage;

    // Resolve ViewOnce
    if (qMsg.viewOnceMessageV2) {
        qMsg = qMsg.viewOnceMessageV2.message;
    } else if (qMsg.viewOnceMessageV2Extension) {
        qMsg = qMsg.viewOnceMessageV2Extension.message;
    } else if (qMsg.viewOnceMessage) {
        qMsg = qMsg.viewOnceMessage.message;
    }

    const mType = Object.keys(qMsg)[0];
    const media = qMsg[mType];

    if (!['imageMessage', 'videoMessage', 'audioMessage'].includes(mType)) {
        return null;
    }

    const mediaType = mType.replace('Message', '');
    const stream = await downloadContentFromMessage(media, mediaType);

    let buffer = Buffer.from([]);
    for await (const chunk of stream) {
        buffer = Buffer.concat([buffer, chunk]);
    }

    return {
        buffer,
        type: mediaType
    };
};



ffmpeg.setFfmpegPath(ffmpegPath);

const tempDir = './temp';
if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir);

export const makeSticker = async (msg) => {
    try {
        const quoted = msg.message?.extendedTextMessage?.contextInfo?.quotedMessage;

        // Detect all media types
        const mediaMessage =
            msg.message?.imageMessage ||
            msg.message?.videoMessage ||
            msg.message?.gifMessage ||
            msg.message?.viewOnceMessageV2?.message?.imageMessage ||
            msg.message?.viewOnceMessageV2?.message?.videoMessage ||
            quoted?.imageMessage ||
            quoted?.videoMessage ||
            quoted?.gifMessage ||
            quoted?.viewOnceMessageV2?.message?.imageMessage ||
            quoted?.viewOnceMessageV2?.message?.videoMessage;

        if (!mediaMessage) return null;

        // Detect video/gif
        const isVideo =
            mediaMessage.mimetype?.includes('video') ||
            mediaMessage.mimetype?.includes('gif') ||
            mediaMessage.seconds;

        const downloadType = isVideo ? 'video' : 'image';

        const stream = await downloadContentFromMessage(mediaMessage, downloadType);

        let buffer = Buffer.from([]);
        for await (const chunk of stream) {
            buffer = Buffer.concat([buffer, chunk]);
        }

        const tempInput = path.join(tempDir, `${uuidv4()}${isVideo ? '.mp4' : '.png'}`);
        fs.writeFileSync(tempInput, buffer);

        const tempOutput = path.join(tempDir, `${uuidv4()}.webp`);

        if (isVideo) {
            await new Promise((resolve, reject) => {
                ffmpeg(tempInput)
                    .outputOptions([
                        '-vcodec libwebp',
                        '-vf scale=512:512:force_original_aspect_ratio=decrease,fps=15',
                        '-loop 0',
                        '-ss 00:00:00',
                        '-t 6',
                        '-preset default',
                        '-an',
                        '-vsync 0'
                    ])
                    .save(tempOutput)
                    .on('end', resolve)
                    .on('error', reject);
            });
        } else {
            await new Promise((resolve, reject) => {
                ffmpeg(tempInput)
                    .outputOptions([
                        '-vcodec libwebp',
                        '-vf scale=512:512:force_original_aspect_ratio=decrease',
                        '-loop 0',
                        '-preset default',
                        '-an',
                        '-vsync 0'
                    ])
                    .save(tempOutput)
                    .on('end', resolve)
                    .on('error', reject);
            });
        }

        const stickerBuffer = fs.readFileSync(tempOutput);

        const sticker = new Sticker(stickerBuffer, {
            pack: 'Nexa-Bot',
            author: 'Arun',
            type: StickerTypes.FULL,
            categories: ['🎨'],
            quality: 40,
        });

        fs.unlinkSync(tempInput);
        fs.unlinkSync(tempOutput);

        return await sticker.toBuffer();

    } catch (err) {
        console.log('Sticker Error:', err);
        return null;
    }
};



