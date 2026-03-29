import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { downloadContentFromMessage } from '@whiskeysockets/baileys'; 
import ffmpeg from 'fluent-ffmpeg';
import { Sticker, StickerTypes } from 'wa-sticker-formatter';
import fs from 'fs';

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


const tempDir = './temp';
if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir); 

export const makeSticker = async (msg) => {
    try {
        
        const quoted = msg.message?.extendedTextMessage?.contextInfo?.quotedMessage;

        // Get media message from different possibilities
        const mediaMessage =
            msg.message?.imageMessage ||
            msg.message?.videoMessage ||
            quoted?.imageMessage ||
            quoted?.videoMessage ||
            quoted?.documentWithCaptionMessage?.message?.videoMessage ||
            quoted?.documentWithCaptionMessage?.message?.imageMessage ||
            msg.message?.viewOnceMessageV2?.message?.imageMessage ||
            msg.message?.viewOnceMessageV2?.message?.videoMessage;

        if (!mediaMessage) return null;

        // Determine if media is a video
        const isVideo = !!(
            mediaMessage.videoMessage ||
            (mediaMessage.mimetype && mediaMessage.mimetype.startsWith('video/'))
        );

        // Download the media into a buffer
        const downloadType = isVideo ? 'video' : 'image';
        const stream = await downloadContentFromMessage(mediaMessage, downloadType);
        let buffer = Buffer.from([]);
        for await (const chunk of stream) {
            buffer = Buffer.concat([buffer, chunk]);
        }

        // Save temporary input file
        const tempInput = path.join(tempDir, `${uuidv4()}${isVideo ? '.mp4' : '.png'}`);
        fs.writeFileSync(tempInput, buffer);

        const tempOutput = path.join(tempDir, `${uuidv4()}.webp`);

        if (isVideo) {
            // Convert video to sticker
            await new Promise((resolve, reject) => {
                ffmpeg(tempInput)
                    .outputOptions([
                        '-vcodec libwebp',
                        '-vf scale=512:512:force_original_aspect_ratio=decrease,fps=15',
                        '-loop 0',
                        '-t 5', 
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
            pack: 'Nexa-Bot MD Pack',
            author: 'arun•°Cumar',
            type: StickerTypes.FULL,
            categories: ['🔥', '✨'],
            id: 'nexa_pro_sticker',
            quality: 30,
        });

        fs.unlinkSync(tempInput);
        fs.unlinkSync(tempOutput);

        return await sticker.toBuffer();
    } catch (error) {
        console.error('Error creating sticker:', error);
        return null;
    }
};




