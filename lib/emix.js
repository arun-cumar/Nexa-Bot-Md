// © 2026 arun•°Cumar. All Rights Reserved.
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function ffmpeg(buffer, args = [], ext = '', ext2 = '') {
    return new Promise(async (resolve, reject) => {
        try {
            // tmp ഫോൾഡർ ഇല്ലെങ്കിൽ ഉണ്ടാക്കാൻ
            const tmpDir = path.join(__dirname, '../tmp/');
            if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir);

            let tmp = path.join(tmpDir, Date.now() + '.' + ext);
            let out = tmp + '.' + ext2;
            
            await fs.promises.writeFile(tmp, buffer);
            
            const process = spawn("ffmpeg", [
                '-y',
                '-i', tmp,
                ...args,
                out
            ]);

            process.on('error', (err) => {
                if (fs.existsSync(tmp)) fs.unlinkSync(tmp);
                reject(err);
            });

            process.on('close', async (code) => {
                try {
                    if (fs.existsSync(tmp)) await fs.promises.unlink(tmp);
                    if (code !== 0) return reject(new Error(`FFMPEG exit code: ${code}`));
                    
                    const data = await fs.promises.readFile(out);
                    if (fs.existsSync(out)) await fs.promises.unlink(out);
                    resolve(data);
                } catch (e) {
                    reject(e);
                }
            });
        } catch (e) {
            reject(e);
        }
    });
}

//  format 
export const toAudio = (buffer, ext) => ffmpeg(buffer, ['-vn', '-ac', '2', '-b:a', '128k', '-ar', '44100', '-f', 'mp3'], ext, 'mp3');
export const toPTT = (buffer, ext) => ffmpeg(buffer, ['-vn', '-c:a', 'libopus', '-b:a', '128k', '-vbr', 'on'], ext, 'opus');
export const toVideo = (buffer, ext) => ffmpeg(buffer, ['-c:v', 'libx264', '-c:a', 'aac', '-crf', '32'], ext, 'mp4');
export const toSticker = (buffer, ext) => ffmpeg(buffer, [
    '-vcodec', 'libwebp', 
    '-vf', "scale='if(gt(a,1),512,-1)':'if(gt(a,1),-1,512)',fps=15,pad=512:512:(512-iw)/2:(512-ih)/2:color=0x00000000",
    '-lossless', '1', 
    '-loop', '0', 
    '-preset', 'default', 
    '-an', '-vsync', '0', 
    '-s', '512:512'
], ext, 'webp');
export const toImage = (buffer, ext) => ffmpeg(buffer, ['-vframes', '1', '-q:v', '2'], ext, 'jpg');
export const toGif = (buffer, ext) => ffmpeg(buffer, [
    '-vf', "fps=10,scale=320:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
    '-loop', '0'
], ext, 'gif');
export const webpToImage = (buffer, ext) => ffmpeg(buffer, [], ext, 'jpg');
