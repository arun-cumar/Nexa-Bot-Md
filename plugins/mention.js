import config from '../config.js';
import axios from 'axios';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegStatic from 'ffmpeg-static';
import fs from 'fs';
import path from 'path';

ffmpeg.setFfmpegPath(ffmpegStatic);

// Hardcoded URLs
const THUMBNAIL_URL = 'https://files.catbox.moe/h3z9as.jpg';
const AUDIO_URL = 'https://files.catbox.moe/jq9z4y.mp3';

const createMentionVideo = async (mentionedJids) => {
    const tempDir = `/tmp/mention_${Date.now()}`;
    const thumbPath = path.join(tempDir, 'thumbnail.jpg');
    const audioPath = path.join(tempDir, 'audio.mp3');
    const videoPath = path.join(tempDir, 'output.mp4');
    
    try {
        fs.mkdirSync(tempDir, { recursive: true });
        
        // Download thumbnail
        const thumbRes = await axios.get(THUMBNAIL_URL, { responseType: 'arraybuffer', timeout: 15000 });
        fs.writeFileSync(thumbPath, thumbRes.data);
        
        // Download audio
        const audioRes = await axios.get(AUDIO_URL, { responseType: 'arraybuffer', timeout: 15000 });
        fs.writeFileSync(audioPath, audioRes.data);
        
        // Create video with FFmpeg
        return new Promise((resolve, reject) => {
            ffmpeg(thumbPath)
                .input(audioPath)
                .inputOptions(['-loop', '1'])
                .outputOptions(['-c:v', 'libx264', '-c:a', 'aac', '-shortest', '-pix_fmt', 'yuv420p'])
                .output(videoPath)
                .on('end', () => {
                    const videoBuffer = fs.readFileSync(videoPath);
                    fs.rmSync(tempDir, { recursive: true });
                    resolve(videoBuffer);
                })
                .on('error', (err) => {
                    fs.rmSync(tempDir, { recursive: true, force: true });
                    reject(err);
                })
                .run();
        });
    } catch (e) {
        if (fs.existsSync(tempDir)) fs.rmSync(tempDir, { recursive: true, force: true });
        throw e;
    }
};

export default async (sock, msg, args, extra) => {
    const chat = msg.key.remoteJid;
    const sender = msg.key.participant || msg.key.remoteJid;

    if (!chat.endsWith('@g.us')) {
        return await sock.sendMessage(chat, { text: '❌ This command works in *groups only*.' }, { quoted: msg });
    }

    try {
        const meta = await sock.groupMetadata(chat);
        const admins = meta.participants.filter(p => p.admin).map(p => p.id);
        const isAdmin = admins.includes(sender);
        const isOwner = config.OWNER_NUMBER.includes(sender.split('@')[0]);

        // If user is admin or owner, mention all normally
        if (isAdmin || isOwner) {
            const members = meta.participants.map(p => p.id);
            const message = args.join(' ') || '👋 Hello everyone!';
            const text = `📢 *Mention All*\n\n${message}\n\n` + members.map(m => `@${m.split('@')[0]}`).join(' ');
            
            return await sock.sendMessage(chat, {
                text,
                mentions: members
            }, { quoted: msg });
        }

        // If user is NOT admin/owner, create audio video with mention
        await sock.sendMessage(chat, { react: { text: '🎬', key: msg.key } });
        
        const members = meta.participants.map(p => p.id);
        const mentionText = members.map(m => `@${m.split('@')[0]}`).join(' ');
        
        const videoBuffer = await createMentionVideo(members);
        
        await sock.sendMessage(chat, {
            video: videoBuffer,
            caption: `👋 ${mentionText}\n\nCheck the audio! 🎵`,
            mentions: members
        }, { quoted: msg });
        
    } catch (e) {
        console.error('Mention Error:', e);
        await sock.sendMessage(chat, { text: '❌ Failed to create mention video.' }, { quoted: msg });
    }
};
